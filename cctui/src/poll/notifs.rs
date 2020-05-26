use crate::settings::{Notif, NotifService, Settings};
use crate::util::StatefulHash;

use log::{debug, error, warn};
use reqwest::blocking::Client;
use serde::Deserialize;
use std::cmp::{max, Ordering};
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
    pub enabled: bool,

    client: Client,
    delay: HashMap<Notif, u16>,
}

impl NotifsPoller {
    pub fn new(settings: &Settings) -> NotifsPoller {
        let delay = match &settings.notifs {
            Some(notifs) => {
                let mut delay = HashMap::with_capacity(notifs.len());
                for repo in notifs.iter() {
                    delay.insert(repo.clone(), 0);
                }
                delay
            }
            _ => HashMap::new(),
        };

        NotifsPoller {
            all: StatefulHash::with_items(BTreeMap::new()),
            enabled: !delay.is_empty(),
            client: Client::new(),
            delay: delay,
        }
    }

    fn make_request(client: &Client, notif: &Notif) -> Option<Vec<StatusItem>> {
        match &notif.service {
            NotifService::Github => {
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
            }
        }
    }

    pub fn get_selected_url(&self) -> Option<String> {
        match self.all.state.selected() {
            Some(i) => match self.all.items.iter().rev().skip(i).next() {
                Some((status, notif)) => match &notif.service {
                    NotifService::Github => {
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
                    }
                },
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
        if !self.enabled {
            return;
        }

        // TODO: until we can do in-place updates, do a bit of debouncing to
        // avoid changing things while the user is interacting
        for (_, val) in self.delay.iter_mut() {
            *val = max(*val, 30);
        }

        match c {
            '\n' => {
                for (_, val) in self.delay.iter_mut() {
                    // force refresh a few seconds after opening a notif
                    // TODO: only refresh the feed that got modified?
                    *val = 30;
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
        if !self.enabled {
            return;
        }

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
