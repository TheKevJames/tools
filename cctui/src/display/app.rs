use crate::settings::Settings;
use crate::util::StatefulHash;

use log::{debug, error};
use reqwest::blocking::Client;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap};

const INTERVAL: u8 = 30;

#[derive(Debug, Deserialize)]
struct Status {
    next_page_token: Option<String>,
    items: Option<Vec<StatusItem>>,
}

#[derive(Debug, Deserialize)]
struct StatusItem {
    id: String,
    status: String,
    duration: u16,
    created_at: String,
    stopped_at: String,
    credits_used: u16,
}

pub struct App<'a> {
    pub title: &'a str,
    pub recent: StatefulHash<String, (String, String)>,
    pub repos: StatefulHash<String, String>,

    poll_delay: HashMap<String, u8>,

    client: Client,
    token: String,
}

impl<'a> App<'a> {
    pub fn new(title: &'a str, settings: Settings) -> App<'a> {
        let mut poll_delay = HashMap::with_capacity(settings.repos.len());
        for repo in settings.repos.iter() {
            poll_delay.insert(repo.clone(), 0);
        }

        App {
            title,
            recent: StatefulHash::with_items(BTreeMap::new()),
            repos: StatefulHash::with_items(
                settings
                    .repos
                    .iter()
                    .map(|r| (r.clone(), "unknown".to_string()))
                    .collect(),
            ),
            poll_delay: poll_delay,
            client: Client::new(),
            token: settings.token.clone(),
        }
    }

    fn make_request(client: &Client, token: String, repo: &str) -> Option<Status> {
        //TODO: configurable
        let url = "https://circleci.com/api/v2/insights/gh/".to_owned()
            + repo
            + "/workflows/run-jobs?branch=master";
        let request = client
            .get(&url)
            .header("Application", "application/json")
            .header("Circle-Token", token);
        match request.send() {
            Ok(resp) => match resp.json() {
                Ok(body) => Some(body),
                Err(e) => {
                    error!("error decoding CI response json: {:?}", e);
                    None
                }
            },
            //TODO: better way to debug than uncommenting this?
            //Ok(resp) => {
            //    println!("{:?}", resp.text());
            //    None
            //},
            Err(e) => {
                error!("error making CI request: {:?}", e);
                None
            }
        }
    }

    pub fn on_key(&mut self, c: char) {
        debug!("keypress: {}", c);
        match c {
            'G' => self.repos.last(),
            'g' => self.repos.first(),
            'j' => self.repos.next(),
            'k' => self.repos.prev(),
            'r' => {
                for (_, val) in self.poll_delay.iter_mut() {
                    *val = 0;
                }
            }
            _ => (),
        }
    }

    pub fn on_tick(&mut self) {
        let mut updates_per_tick: u8 = 3; //TODO: tune
        for (repo, val) in self.poll_delay.iter_mut() {
            if val == &0 {
                if updates_per_tick == 0 {
                    continue;
                }

                //TODO: async
                match Self::make_request(&self.client, self.token.clone(), &repo) {
                    Some(status) => {
                        match status.items {
                            Some(items) if items.len() > 0 => {
                                self.repos
                                    .items
                                    .insert(repo.clone(), items[0].status.clone());
                                for job in items {
                                    //TODO: get branch info
                                    self.recent
                                        .items
                                        .insert(job.stopped_at, (repo.clone(), job.status));
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
                                // warn!("got unknown CI status for {}", repo.clone());
                                self.repos.items.insert(repo.clone(), "unknown".to_string());
                                ()
                            }
                        }
                        updates_per_tick -= 1;
                        *val = INTERVAL;
                    }
                    //TODO: backoff with retry
                    None => (),
                }
                continue;
            }

            *val -= 1;
        }
    }
}
