use ratatui::widgets::ListState;
use std::cmp::{max, min};
use std::collections::BTreeMap;
use std::fmt::Debug;

#[derive(Debug, Clone)]
pub struct FilteredListState {
    offset: usize,
    selected: Option<usize>,

    public: ListState,
}

impl Default for FilteredListState {
    fn default() -> FilteredListState {
        FilteredListState {
            offset: 0,
            selected: None,
            public: ListState::default(),
        }
    }
}

impl FilteredListState {
    pub fn selected(&self) -> Option<usize> {
        self.selected
    }

    pub fn select(&mut self, index: Option<usize>, findex: Option<usize>) {
        self.selected = index;
        if index.is_none() {
            self.offset = 0;
        }
        self.public.select(None); // hack: self.public.offset = 0;
        self.public.select(findex);
    }
}

impl std::ops::Deref for FilteredListState {
    type Target = ListState;
    fn deref(&self) -> &Self::Target {
        &self.public
    }
}

impl std::ops::DerefMut for FilteredListState {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.public
    }
}

pub struct StatefulList<T> {
    pub state: FilteredListState,
    pub items: Vec<T>,
}

impl<T> StatefulList<T> {
    pub fn with_items(items: Vec<T>) -> StatefulList<T> {
        StatefulList {
            state: FilteredListState::default(),
            items: items,
        }
    }

    pub fn first(&mut self) {
        let target = Some(0);
        self.state.select(target, target);
    }

    pub fn last(&mut self) {
        let target = Some(self.items.len() - 1);
        self.state.select(target, target);
    }

    pub fn next(&mut self) {
        match self.state.selected() {
            Some(curr) => {
                let target = Some(min(curr + 1, self.items.len()));
                self.state.select(target, target);
            }
            None => self.first(),
        }
    }

    pub fn prev(&mut self) {
        match self.state.selected() {
            Some(curr) => {
                let target = Some(max(curr - 1, 0));
                self.state.select(target, target);
            }
            None => self.first(),
        }
    }
}

pub struct StatefulHash<T, V> {
    pub state: FilteredListState,
    pub items: BTreeMap<T, (V, bool)>,
}

impl<T: Debug, V: Debug> StatefulHash<T, V> {
    pub fn with_items(items: BTreeMap<T, (V, bool)>) -> StatefulHash<T, V> {
        StatefulHash {
            state: FilteredListState::default(),
            items: items,
        }
    }

    pub fn first(&mut self) {
        for (i, (_, (_, visible))) in self.items.iter().enumerate() {
            if *visible {
                self.state.select(Some(i), Some(0));
                return;
            }
        }
        self.state.select(Some(0), Some(0));
    }

    pub fn last(&mut self) {
        for (i, (_, (_, visible))) in self.items.iter().rev().enumerate() {
            if *visible {
                let target = self.items.len() - 1 - i;
                let count = self.items.iter().filter(|(_, (_, vis))| *vis).count();
                self.state.select(Some(target), Some(count - 1));
                return;
            }
        }
        let target = self.items.len() - 1;
        self.state.select(Some(target), Some(target));
    }

    pub fn next(&mut self) {
        match self.state.selected() {
            Some(curr) => {
                let mut idx = 0;
                for (i, (_, (_, visible))) in self.items.iter().enumerate() {
                    if *visible {
                        idx += 1;
                        if i <= curr {
                            continue;
                        }
                        self.state.select(Some(i), Some(idx - 1));
                        return;
                    }
                }
                self.first();
            }
            None => self.first(),
        }
    }

    pub fn prev(&mut self) {
        match self.state.selected() {
            Some(curr) => {
                let mut idx = 0;
                for (i, (_, (_, visible))) in self.items.iter().rev().enumerate() {
                    if *visible {
                        idx += 1;
                        let target = self.items.len() - 1 - i;
                        if target >= curr {
                            continue;
                        }
                        let count = self.items.iter().filter(|(_, (_, vis))| *vis).count();
                        self.state.select(Some(target), Some(count - idx));
                        return;
                    }
                }
                self.last();
            }
            None => self.first(),
        }
    }
}
