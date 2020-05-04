use crate::settings::{Notif, Settings};
use crate::util::StatefulHash;

use reqwest::blocking::Client;
use std::collections::{BTreeMap, HashMap};

pub struct NotifsPoller {
    pub all: StatefulHash<Notif, u8>,

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

    pub fn on_tick(&mut self, mut allow_processing: bool) {}
}
