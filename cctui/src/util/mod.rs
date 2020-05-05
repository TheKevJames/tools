pub mod event;

use std::collections::BTreeMap;
use tui::widgets::ListState;

pub struct StatefulList<T> {
    pub state: ListState,
    pub items: Vec<T>,
}

impl<T> StatefulList<T> {
    pub fn with_items(items: Vec<T>) -> StatefulList<T> {
        StatefulList {
            state: ListState::default(),
            items: items,
        }
    }

    pub fn first(&mut self) {
        self.state.select(Some(0));
    }

    // pub fn last(&mut self) {
    //     self.state.select(Some(self.items.len() - 1));
    // }

    pub fn next(&mut self) {
        let i = match self.state.selected() {
            Some(i) => {
                if i >= self.items.len() - 1 {
                    0
                } else {
                    i + 1
                }
            }
            None => 0,
        };
        self.state.select(Some(i));
    }

    // pub fn prev(&mut self) {
    //     let i = match self.state.selected() {
    //         Some(i) => {
    //             if i == 0 {
    //                 self.items.len() - 1
    //             } else {
    //                 i - 1
    //             }
    //         }
    //         None => 0,
    //     };
    //     self.state.select(Some(i));
    // }
}

pub struct StatefulHash<T, V> {
    pub state: ListState,
    pub items: BTreeMap<T, V>,
}

impl<T, V> StatefulHash<T, V> {
    pub fn with_items(items: BTreeMap<T, V>) -> StatefulHash<T, V> {
        StatefulHash {
            state: ListState::default(),
            items: items,
        }
    }

    pub fn first(&mut self) {
        self.state.select(Some(0));
    }

    pub fn last(&mut self) {
        self.state.select(Some(self.items.len() - 1));
    }

    pub fn next(&mut self) {
        let i = match self.state.selected() {
            Some(i) => {
                if i >= self.items.len() - 1 {
                    0
                } else {
                    i + 1
                }
            }
            None => 0,
        };
        self.state.select(Some(i));
    }

    pub fn prev(&mut self) {
        let i = match self.state.selected() {
            Some(i) => {
                if i == 0 {
                    self.items.len() - 1
                } else {
                    i - 1
                }
            }
            None => 0,
        };
        self.state.select(Some(i));
    }
}
