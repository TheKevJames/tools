use crate::poll::{NotifsPoller, ReposPoller};
use crate::settings::Settings;

use log::{error, info};
use std::process::Command;

pub struct App {
    pub notifs: NotifsPoller,
    pub repos: ReposPoller,
}

impl App {
    pub fn new(settings: &Settings) -> App {
        App {
            notifs: NotifsPoller::new(settings),
            repos: ReposPoller::new(settings),
        }
    }

    fn browse(&mut self) {
        // TODO: notifs
        let url = self.repos.get_selected_url();
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
        self.notifs.on_key(c);
        self.repos.on_key(c);
        match c {
            '\n' => self.browse(),
            _ => (),
        }
    }

    pub fn on_tick(&mut self) {
        // TODO: timeslice different pollers?
        self.notifs.on_tick(true);
        self.repos.on_tick(true);
    }
}
