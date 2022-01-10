use crate::poll::{NotifsPoller, ReposPoller};
use crate::settings::Settings;
use crate::util::StatefulList;

use log::{error, info};
use std::cmp::{max, min};
use std::process::Command;
use termion::event::Key;

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

    fn resize(&mut self, c: char) {
        self.visible_notifs = match c {
            'J' => min(self.visible_notifs + 1, 9999), // TODO: max based on screen size to prevent panic
            'K' => max(self.visible_notifs - 1, 1),
            _ => self.visible_notifs,
        }
    }

    pub fn on_key(&mut self, key: Key) -> bool {
        // TODO: fixup ugly return value handling
        match key {
            Key::Backspace => match self.state.state.selected() {
                Some(2) => {
                    self.filter.pop();
                    true
                }
                _ => false,
            },
            Key::Char(c) => {
                match self.state.state.selected() {
                    Some(0) => {
                        self.notifs.on_key(c);
                        match c {
                            '/' => {
                                self.filter.clear();
                                self.state.last();
                                true
                            }
                            '\n' => {
                                self.browse();
                                true
                            }
                            '\t' => {
                                self.state.next();
                                true
                            }
                            'J' | 'K' => {
                                self.resize(c);
                                true
                            }
                            _ => false,
                        }
                    }
                    Some(1) => {
                        self.repos.on_key(c);
                        match c {
                            '/' => {
                                self.filter.clear();
                                self.state.last();
                                true
                            }
                            '\n' => {
                                self.browse();
                                true
                            }
                            '\t' => {
                                self.state.prev();
                                true
                            }
                            'J' | 'K' => {
                                self.resize(c);
                                true
                            }
                            _ => false,
                        }
                    }
                    Some(2) => {
                        match c {
                            '\n' => {
                                self.notifs.filter(&self.filter);
                                self.repos.filter(&self.filter);
                                self.state.first();
                                true
                            }
                            '\t' => false,
                            _ => {
                                // TODO: consider applying filters on each key press
                                self.filter.push(c);
                                true
                            }
                        }
                    }
                    _ => false,
                }
            }
            _ => false,
        }
    }

    pub fn on_tick(&mut self) {
        // TODO: timeslice different pollers?
        self.notifs.on_tick(true);
        self.repos.on_tick(true);
    }
}
