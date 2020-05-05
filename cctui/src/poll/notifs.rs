use crate::settings::{Notif, Settings};
use crate::util::StatefulHash;

use log::{debug, error, warn};
use reqwest::blocking::Client;
use serde::Deserialize;
use std::cmp::{min, Ordering};
use std::collections::{BTreeMap, HashMap};

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, PartialOrd)]
pub struct Subject {
    pub title: String,
    pub url: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, PartialOrd)]
pub struct Repository {
    pub full_name: String,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, PartialOrd)]
pub struct StatusItem {
    id: String,
    pub reason: String,
    pub repository: Repository,
    pub subject: Subject,
    updated_at: String,
}
impl Ord for StatusItem {
    fn cmp(&self, other: &Self) -> Ordering {
        self.updated_at.cmp(&other.updated_at)
    }
}

#[derive(Debug, Deserialize)]
pub struct GithubNotifLookup {
    html_url: String,
}

pub struct NotifsPoller {
    pub all: StatefulHash<StatusItem, Notif>,

    client: Client,
    delay: HashMap<Notif, u16>,
}

impl NotifsPoller {
    pub fn new(settings: &Settings) -> NotifsPoller {
        let mut delay = HashMap::with_capacity(settings.notifs.len());
        for repo in settings.notifs.iter() {
            delay.insert(repo.clone(), 0);
        }

        NotifsPoller {
            all: StatefulHash::with_items(BTreeMap::new()),
            client: Client::new(),
            delay: delay,
        }
    }

    fn make_request(client: &Client, notif: &Notif) -> Option<Vec<StatusItem>> {
        if &notif.service == "github" {
            let url = "https://api.github.com/notifications";
            let request = client
                .get(url)
                .header("User-Agent", "CCTUI")
                .header("Authorization", format!("Bearer {}", &notif.token));
            match request.send() {
                Ok(resp) => match resp.json() {
                    Ok(body) => Some(body),
                    Err(e) => {
                        error!("error decoding Github response json: {:?}", e);
                        None
                    }
                },
                Err(e) => {
                    error!("error making Github request: {:?}", e);
                    None
                }
            }
        } else {
            error!("invalid config for: {}", notif.service);
            None
        }
    }

    pub fn get_selected_url(&self) -> Option<String> {
        match self.all.state.selected() {
            Some(i) => match self.all.items.iter().rev().skip(i).next() {
                Some((status, notif)) => {
                    if &notif.service == "github" {
                        debug!("fetching user-facing URL from {}", status.subject.url);
                        let request = self
                            .client
                            .get(&status.subject.url)
                            .header("User-Agent", "CCTUI")
                            .header("Authorization", format!("Bearer {}", &notif.token));
                        match request.send() {
                            Ok(resp) => match resp.json() {
                                Ok(body) => {
                                    let lookup: GithubNotifLookup = body;
                                    Some(lookup.html_url)
                                }
                                Err(e) => {
                                    error!("could not retrieve user-facing URL: {:?}", e);
                                    None
                                }
                            },
                            Err(e) => {
                                error!("error making Github request: {:?}", e);
                                None
                            }
                        }
                    } else {
                        None
                    }
                }
                None => {
                    error!(
                        "attempted to browse to notif {} of {}",
                        i,
                        self.all.items.len() - 1
                    );
                    None
                }
            },
            None => {
                warn!("attempted to browse to unselected notif");
                None
            }
        }
    }

    pub fn on_key(&mut self, c: char) {
        match c {
            '\n' => {
                for (_, val) in self.delay.iter_mut() {
                    // refresh a few seconds after opening a notif
                    *val = min(*val, 30);
                }
            }
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
        for (notif, val) in self.delay.iter_mut() {
            if val == &0 {
                if !allow_processing {
                    continue;
                }

                if let Some(items) = Self::make_request(&self.client, &notif) {
                    // TODO: do an in-place refresh instead of wiping everything
                    self.all.items.clear();
                    for item in items {
                        self.all.items.insert(item.clone(), notif.clone());
                    }
                    self.all.first();
                }

                allow_processing = false;
                *val = notif.refresh * 10; // 10 ticks per second
            }

            *val -= 1
        }
    }
}
