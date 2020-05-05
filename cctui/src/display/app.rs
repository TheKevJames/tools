use crate::poll::{NotifsPoller, ReposPoller};
use crate::settings::Settings;
use crate::util::StatefulList;

use log::{error, info};
use std::process::Command;

pub struct App {
    pub notifs: NotifsPoller,
    pub repos: ReposPoller,

    pub state: StatefulList<&'static str>,
}

impl App {
    pub fn new(settings: &Settings) -> App {
        // N.B. must match expected order in UI
        let mut state = StatefulList::with_items(vec!["Notifs", "Repos"]);
        state.first();
        App {
            notifs: NotifsPoller::new(settings),
            repos: ReposPoller::new(settings),
            state: state,
        }
    }

    fn browse(&mut self) {
        let url = match self.state.state.selected() {
            Some(0) => self.notifs.get_selected_url(),
            Some(1) => self.repos.get_selected_url(),
            _ => None,
        };
        match url {
            Some(url) => {
                info!("opening browser to: {}", url);
                match Command::new("open").arg(url).output() {
                    Ok(_) => (),
                    Err(e) => error!("failed to open browser: {:?}", e),
                }
            }
            None => error!("attempted to browse with no item selected"),
        }
    }

    pub fn on_key(&mut self, c: char) {
        match self.state.state.selected() {
            Some(0) => self.notifs.on_key(c),
            Some(1) => self.repos.on_key(c),
            _ => (),
        };
        match c {
            '\n' => self.browse(),
            '\t' => self.state.next(),
            _ => (),
        }
    }

    pub fn on_tick(&mut self) {
        // TODO: timeslice different pollers?
        self.notifs.on_tick(true);
        self.repos.on_tick(true);
    }
}
