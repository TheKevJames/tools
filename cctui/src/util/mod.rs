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
}
