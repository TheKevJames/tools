use crate::settings::{Notif, NotifService, Settings};
use crate::util::StatefulHash;

use crossterm::event::KeyCode;
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
    polling: bool,
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
            polling: !delay.is_empty(),
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
            Some(i) => {
                match self.all.items.iter().skip(i).next() {
                    Some((status, (notif, _))) => match &notif.service {
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
                        // impossible
                        error!(
                            "attempted to browse to notif {} of {}",
                            i,
                            self.all.items.len() - 1
                        );
                        None
                    }
                }
            }
            None => {
                warn!("attempted to browse to unselected notif");
                None
            }
        }
    }

    pub fn filter(&mut self, filter: &str) {
        self.polling = filter.is_empty() && !self.delay.is_empty();
        if self.polling {
            // In case we've been filtered for a while, make sure to update
            // soon after un-filtering
            // TODO: once we can do in-place upgrades, we should be able to
            // avoid toggling off polling while filtered
            for (_, val) in self.delay.iter_mut() {
                *val = max(*val, 10);
            }
        }

        for (status, (_, visible)) in self.all.items.iter_mut() {
            let show = {
                if filter.chars().count() > 0 && &filter[0..1] == "!" {
                    if filter.chars().count() > 1 {
                        !status.repository.full_name.contains(&filter[1..])
                            && !status.subject.title.contains(&filter[1..])
                            && !status.reason.contains(&filter[1..])
                    } else {
                        true
                    }
                } else {
                    status.repository.full_name.contains(filter)
                        || status.subject.title.contains(filter)
                        || status.reason.contains(filter)
                }
            };
            *visible = show;
        }
        self.all.first();
    }

    pub fn on_key(&mut self, key: KeyCode) {
        if !self.enabled {
            return;
        }

        // TODO: until we can do in-place updates, do a bit of debouncing to
        // avoid changing things while the user is interacting
        for (_, val) in self.delay.iter_mut() {
            *val = max(*val, 30);
        }

        match key {
            KeyCode::Enter => {
                for (_, val) in self.delay.iter_mut() {
                    // force refresh a few seconds after opening a notif
                    // TODO: only refresh the feed that got modified?
                    *val = 30;
                }
            }
            KeyCode::Char('G') => self.all.last(),
            KeyCode::Char('g') => self.all.first(),
            KeyCode::Char('j') => self.all.next(),
            KeyCode::Char('k') => self.all.prev(),
            KeyCode::Char('r') => {
                for (_, val) in self.delay.iter_mut() {
                    *val = 0;
                }
            }
            _ => (),
        }
    }

    pub fn on_tick(&mut self, mut allow_processing: bool) {
        if !self.polling {
            return;
        }

        for (notif, val) in self.delay.iter_mut() {
            if val == &0 {
                if !allow_processing {
                    continue;
                }

                debug!("fetching notifications for {}", notif.service);
                if let Some(items) = Self::make_request(&self.client, &notif) {
                    self.all.items = self
                        .all
                        .items
                        .clone()
                        .into_iter()
                        .filter(|(i, (n, _))| &n != &notif || items.contains(&i))
                        .collect();
                    for item in items {
                        self.all.items.insert(item.clone(), (notif.clone(), true));
                    }
                    // TODO: keep pointing at the current element
                    // concerns to address:
                    // - current element was removed
                    // - any items were inserted or removed above our current index
                    self.all.first();
                }

                allow_processing = false;
                *val = notif.refresh * 10; // 10 ticks per second
            }

            *val -= 1
        }
    }
}
