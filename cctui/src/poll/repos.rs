use crate::settings::{Repo, Settings};
use crate::util::StatefulHash;

use log::{error, warn};
use reqwest::blocking::Client;
use serde::Deserialize;
use serde_xml_rs::from_str;
use std::cmp::Ordering;
use std::collections::{BTreeMap, HashMap};

#[derive(Clone, Debug, Eq, PartialEq, PartialOrd)]
pub struct StatusItem {
    // TODO: status: Enum { Cancelled, Failed, .. }
    pub status: &'static str,
    timestamp: String,
    url: Option<String>,
}
impl StatusItem {
    fn new(status: &'static str) -> Self {
        StatusItem {
            status: status,
            timestamp: String::from(""),
            url: None,
        }
    }

    fn with_timestamp(mut self, timestamp: String) -> Self {
        self.timestamp = timestamp;
        self
    }

    fn with_url(mut self, url: String) -> Self {
        self.url = Some(url);
        self
    }
}
impl Ord for StatusItem {
    fn cmp(&self, other: &Self) -> Ordering {
        self.timestamp.cmp(&other.timestamp)
    }
}

#[derive(Debug)]
struct Status {
    items: Option<Vec<StatusItem>>,
}

#[derive(Debug, Deserialize)]
struct CCTrayStatusItem {
    activity: String,
    #[serde(rename = "lastBuildLabel")]
    last_build_label: String,
    #[serde(rename = "lastBuildStatus")]
    last_build_status: String,
    #[serde(rename = "lastBuildTime")]
    last_build_time: String,
    name: String,
    #[serde(rename = "webUrl")]
    web_url: String,
}
impl From<&CCTrayStatusItem> for StatusItem {
    fn from(src: &CCTrayStatusItem) -> Self {
        let status = match src.last_build_status.as_str() {
            "Exception" | "Unknown" => "error",
            "Failure" => "failed",
            "Success" => "success",
            x => {
                warn!("got unhandled CCTray status: {}", x);
                "unknown"
            }
        };
        StatusItem::new(status)
            .with_timestamp(src.last_build_time.clone())
            .with_url(src.web_url.clone())
    }
}

#[derive(Debug, Deserialize)]
struct CCTrayStatus {
    #[serde(rename = "Project")]
    projects: Vec<CCTrayStatusItem>,
}
impl CCTrayStatus {
    fn filter_repo(self, repo: &str) -> Self {
        let projects = self
            .projects
            .into_iter()
            .filter(|x| x.name.as_str() == repo)
            .collect();
        CCTrayStatus { projects: projects }
    }
}
impl From<CCTrayStatus> for Status {
    fn from(src: CCTrayStatus) -> Self {
        Status {
            items: Some(src.projects.iter().map(|x| StatusItem::from(x)).collect()),
        }
    }
}

#[derive(Debug, Deserialize)]
struct CircleCIStatusItem {
    id: String,
    status: String,
    duration: u16,
    created_at: String,
    stopped_at: String,
    credits_used: u16,
}
impl From<&CircleCIStatusItem> for StatusItem {
    fn from(src: &CircleCIStatusItem) -> Self {
        let status = match src.status.as_str() {
            "canceled" | "cancelled" | "failed" => "failed",
            "error" | "unauthorized" => "error",
            "success" => "success",
            x => {
                warn!("got unhandled CircleCI status: {}", x);
                "unknown"
            }
        };
        StatusItem::new(status).with_timestamp(src.stopped_at.clone())
    }
}

#[derive(Debug, Deserialize)]
struct CircleCIStatus {
    next_page_token: Option<String>,
    items: Option<Vec<CircleCIStatusItem>>,
}
impl From<CircleCIStatus> for Status {
    fn from(src: CircleCIStatus) -> Self {
        Status {
            items: match src.items {
                Some(xs) => Some(xs.iter().map(|x| StatusItem::from(x)).collect()),
                None => None,
            },
        }
    }
}

pub struct ReposPoller {
    pub all: StatefulHash<Repo, StatusItem>,
    pub recent: StatefulHash<StatusItem, Repo>,

    client: Client,
    delay: HashMap<Repo, u16>,
}

impl ReposPoller {
    pub fn new(settings: &Settings) -> ReposPoller {
        // remove invalid configurations
        let repos: Vec<Repo> = settings
            .repos
            .clone()
            .into_iter()
            .filter(|r| r.cctray.is_some() || r.circleci.is_some())
            .collect();

        let mut delay = HashMap::with_capacity(repos.len());
        for repo in repos.iter() {
            delay.insert(repo.clone(), 0);
        }

        ReposPoller {
            all: StatefulHash::with_items(
                repos
                    .iter()
                    .map(|r| (r.clone(), StatusItem::new("unknown")))
                    .collect(),
            ),
            recent: StatefulHash::with_items(BTreeMap::new()),
            client: Client::new(),
            delay: delay,
        }
    }

    fn make_request(client: &Client, repo: &Repo) -> Option<Status> {
        // TODO: ugly
        if let Some(cctray) = &repo.cctray {
            let request = client.get(&cctray.url);
            match request.send() {
                Ok(resp) => match resp.text() {
                    Ok(body) => {
                        let status: CCTrayStatus = match from_str(&body) {
                            Ok(x) => x,
                            Err(e) => {
                                error!("error decoding CCTray response text: {:?}", e);
                                return None;
                            }
                        };
                        Some(Status::from(status.filter_repo(&repo.name)))
                    }
                    Err(e) => {
                        error!("error decoding CCTray response text: {:?}", e);
                        None
                    }
                },
                Err(e) => {
                    error!("error making CCTray request: {:?}", e);
                    None
                }
            }
        } else if let Some(circleci) = &repo.circleci {
            let url = format!(
                "https://circleci.com/api/v2/insights/{}/{}/workflows/{}?branch={}",
                circleci.vcs, repo.name, circleci.workflow, circleci.branch
            );
            let request = client
                .get(&url)
                .header("Application", "application/json")
                .header("Circle-Token", &circleci.token);
            match request.send() {
                Ok(resp) => match resp.json() {
                    Ok(body) => {
                        let status: CircleCIStatus = body;
                        Some(Status::from(status))
                    }
                    Err(e) => {
                        error!("error decoding CircleCI response json: {:?}", e);
                        None
                    }
                },
                Err(e) => {
                    error!("error making CircleCI request: {:?}", e);
                    None
                }
            }
        } else {
            error!("invalid config for: {}", repo.name);
            None
        }
    }

    pub fn get_selected_url(&self) -> Option<String> {
        match self.all.state.selected() {
            Some(i) => match self.all.items.iter().skip(i).next() {
                Some((repo, status)) => {
                    let chunks = repo.name.split("/").collect::<Vec<_>>();
                    match &status.url {
                        Some(x) => Some(x.clone()),
                        None => {
                            if let Some(circleci) = &repo.circleci {
                                // TODO: move into status.url
                                Some(format!(
                                    "https://circleci.com/{}/{}/workflows/{}/tree/{}",
                                    circleci.vcs, chunks[0], chunks[1], circleci.branch
                                ))
                            } else {
                                error!("no url configured for: {}", repo.name);
                                None
                            }
                        }
                    }
                }
                None => {
                    error!(
                        "attempted to browse to repo {} of {}",
                        i,
                        self.all.items.len() - 1
                    );
                    None
                }
            },
            None => {
                warn!("attempted to browse to unselected repo");
                None
            }
        }
    }

    pub fn on_key(&mut self, c: char) {
        match c {
            'G' => self.all.last(),
            'g' => self.all.first(),
            'j' => self.all.next(),
            'k' => self.all.prev(),
            'r' => {
                for (_, val) in self.delay.iter_mut() {
                    *val = 0;
                }
            }
            _ => (),
        }
    }

    pub fn on_tick(&mut self, mut allow_processing: bool) {
        for (repo, val) in self.delay.iter_mut() {
            if val == &0 {
                if !allow_processing {
                    continue;
                }

                // TODO: async then consider multiple updates per tick?
                match Self::make_request(&self.client, &repo) {
                    Some(status) => {
                        match status.items {
                            Some(items) if items.len() > 0 => {
                                self.all.items.insert(repo.clone(), items[0].clone());
                                for job in items {
                                    self.recent.items.insert(job, repo.clone());
                                    if self.recent.items.len() > 5 {
                                        let entry = match self.recent.items.iter().next() {
                                            Some((k, _)) => Some(k.clone()),
                                            _ => None,
                                        };
                                        if entry.is_some() {
                                            self.recent.items.remove(&entry.unwrap());
                                        }
                                    }
                                }
                            }
                            _ => {
                                // TODO: figure out how to grab most recent run from >90 days ago
                                // warn!("got unknown CI status for {}", repo.name);
                                self.all
                                    .items
                                    .insert(repo.clone(), StatusItem::new("unknown"));
                                ()
                            }
                        }
                        allow_processing = false; // be kind to our event loop
                        *val = repo.refresh * 10; // 10 ticks per second
                    }
                    // TODO: should we add a backoff handler?
                    None => (),
                }
                continue;
            }

            *val -= 1;
        }
    }
}
