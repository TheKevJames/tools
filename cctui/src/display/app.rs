use crate::poll::{NotifsPoller, ReposPoller};
use crate::settings::Settings;
use crate::util::StatefulList;

use crossterm::event::KeyCode;
use log::{error, info};
use std::cmp::{max, min};
use std::process::Command;

pub struct App {
    pub filter: String,
    pub notifs: NotifsPoller,
    pub repos: ReposPoller,

    pub state: StatefulList<&'static str>,
    pub visible_notifs: u16,
}

impl App {
    pub fn new(settings: &Settings) -> App {
        let mut state = StatefulList::with_items(vec!["Notifs", "Repos", "Filter"]);
        state.first();
        App {
            filter: String::new(),
            notifs: NotifsPoller::new(settings),
            repos: ReposPoller::new(settings),
            state: state,
            visible_notifs: settings.layout.visible_notifs,
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

    pub fn on_key(&mut self, key: KeyCode) {
        match self.state.state.selected() {
            Some(0) => self.notifs.on_key(key),
            Some(1) => self.repos.on_key(key),
            Some(2) => {
                match key {
                    KeyCode::Backspace => _ = self.filter.pop(),
                    KeyCode::Enter => {
                        self.notifs.filter(&self.filter);
                        self.repos.filter(&self.filter);
                        self.state.first();
                    },
                    KeyCode::Char(c) => self.filter.push(c),
                    _ => (),
                }
                return;
            },
            _ => (),
        }
        match key {
            KeyCode::Enter => self.browse(),
            KeyCode::Tab => match self.state.state.selected() {
                Some(0) => self.state.next(),
                Some(1) => self.state.prev(),
                _ => (),
            },
            KeyCode::Char('/') => {
                self.filter.clear();
                self.state.last();
            },
            KeyCode::Char('J') => self.visible_notifs = min(self.visible_notifs + 1, 20),
            KeyCode::Char('K') => self.visible_notifs = max(self.visible_notifs - 1, 1),
            _ => (),
        }
    }

    pub fn on_tick(&mut self) {
        // TODO: timeslice different pollers?
        self.notifs.on_tick(true);
        self.repos.on_tick(true);
    }
}
