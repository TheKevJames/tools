use crate::display::App;

use log::warn;
use tui::backend::Backend;
use tui::layout::{Constraint, Direction, Layout, Rect};
use tui::style::{Color, Style};
use tui::widgets::{Block, Borders, List, Text};
use tui::Frame;

pub fn draw<B: Backend>(f: &mut Frame<B>, app: &mut App) {
    let chunks = Layout::default()
        .constraints([Constraint::Min(7), Constraint::Length(7)].as_ref())
        .split(f.size());

    //TODO: allow cursor to open build pages
    draw_repos(f, app, chunks[0]);
    draw_recent(f, app, chunks[1]);
}

fn draw_repos<B: Backend>(f: &mut Frame<B>, app: &mut App, area: Rect) {
    //TODO: config to hide green
    let style_error = Style::default().fg(Color::Magenta);
    let style_failure = Style::default().fg(Color::Red);
    let style_success = Style::default().fg(Color::Green);
    let style_unknown = Style::default().fg(Color::White);
    let mut repos = app.repos.items.iter().map(|(repo, level)| {
        Text::styled(
            format!("{}", repo),
            match level.as_ref() {
                "cancelled" => style_error,
                "error" => style_error,
                "failed" => style_failure,
                "success" => style_success,
                "unauthorized" => style_error,
                _ => style_unknown,
            },
        )
    });

    let columns = ((app.repos.items.len() as u16) + area.height - 1) / area.height; //TODO: large values
    let constraints = vec![Constraint::Percentage(100 / columns); columns as usize];
    let chunks = Layout::default()
        .constraints(constraints)
        .direction(Direction::Horizontal)
        .split(area);

    for chunk in chunks {
        let rows = repos.by_ref().take(area.height as usize);
        let rows = List::new(rows).block(
            Block::default()
                .borders(Borders::ALL)
                .title(" Repo Status "),
        );

        f.render_stateful_widget(rows, chunk, &mut app.recent.state);
    }
}

fn draw_recent<B: Backend>(f: &mut Frame<B>, app: &mut App, area: Rect) {
    let style_error = Style::default().fg(Color::Magenta);
    let style_failure = Style::default().fg(Color::Red);
    let style_success = Style::default().fg(Color::Green);
    let style_unknown = Style::default().fg(Color::White);
    let repos = app.recent.items.iter().rev().map(|(_, (repo, level))| {
        Text::styled(
            format!("{}", repo),
            match level.as_ref() {
                "cancelled" => style_error,
                "error" => style_error,
                "failed" => style_failure,
                "success" => style_success,
                "unauthorized" => style_error,
                _ => {
                    //TODO: enum, move this error out of ui layer
                    warn!("got unknown repo status: {} -> {}", repo, level);
                    style_unknown
                }
            },
        )
    });

    let rows = List::new(repos).block(
        Block::default()
            .borders(Borders::ALL)
            .title(" Recent Workflows "),
    );

    f.render_stateful_widget(rows, area, &mut app.recent.state);
}
