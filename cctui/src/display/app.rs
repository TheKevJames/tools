use crate::poll::ReposPoller;
use crate::settings::Settings;

use log::{error, info};
use std::process::Command;

pub struct App {
    pub repos: ReposPoller,
}

impl App {
    pub fn new(settings: Settings) -> App {
        App {
            repos: ReposPoller::new(settings),
        }
    }

    fn browse(&mut self) {
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
        self.repos.on_key(c);
        match c {
            '\n' => self.browse(),
            _ => (),
        }
    }

    pub fn on_tick(&mut self) {
        self.repos.on_tick(true);
    }
}
