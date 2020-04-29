pub mod event;

use std::collections::BTreeMap;
use tui::widgets::ListState;

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
