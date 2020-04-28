use tui::{
    backend::Backend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Style},
    widgets::{Block, Borders, List, Text},
    Frame,
};

use crate::display::App;

pub fn draw<B: Backend>(f: &mut Frame<B>, app: &mut App) {
    let chunks = Layout::default()
        .constraints([Constraint::Min(7), Constraint::Length(7)].as_ref())
        .split(f.size());

    draw_repos(f, app, chunks[0]);
    draw_recent(f, app, chunks[1]);
}

fn draw_repos<B: Backend>(f: &mut Frame<B>, app: &mut App, area: Rect) {
    let style_unk = Style::default().fg(Color::White);
    let style_ok = Style::default().fg(Color::Green);
    let style_err = Style::default().fg(Color::Red);

    //TODO: auto-chunk into columns
    let chunks = Layout::default()
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)].as_ref())
        .direction(Direction::Horizontal)
        .split(area);

    let repos0 = app
        .repos
        .items
        .iter()
        .take(app.repos.items.len() / 2)
        .map(|(repo, level)| {
            Text::styled(
                format!("{}", repo),
                match level.as_ref() {
                    "success" => style_ok,
                    "failed" => style_err,
                    _ => style_unk,
                },
            )
        });
    let repos0 = List::new(repos0).block(
        Block::default()
            .borders(Borders::ALL)
            .title(" Repo Status "),
    );
    let repos1 = app
        .repos
        .items
        .iter()
        .skip(app.repos.items.len() / 2)
        .map(|(repo, level)| {
            Text::styled(
                //TODO: tabular
                //TODO: alphabetize
                format!("{}", repo),
                match level.as_ref() {
                    "success" => style_ok,
                    "failed" => style_err,
                    _ => style_unk,
                },
            )
        });
    let repos1 = List::new(repos1).block(
        Block::default()
            .borders(Borders::ALL)
            .title(" Repo Status "),
    );

    f.render_stateful_widget(repos0, chunks[0], &mut app.recent.state);
    f.render_stateful_widget(repos1, chunks[1], &mut app.recent.state);
}

fn draw_recent<B: Backend>(f: &mut Frame<B>, app: &mut App, area: Rect) {
    // Draw logs
    let info_style = Style::default().fg(Color::White);
    let warning_style = Style::default().fg(Color::Yellow);
    let error_style = Style::default().fg(Color::Magenta);
    let critical_style = Style::default().fg(Color::Red);
    let logs = app.recent.items.iter().map(|(evt, level)| {
        Text::styled(
            format!("{}: {}", level, evt),
            match level.as_ref() {
                "ERROR" => error_style,
                "CRITICAL" => critical_style,
                "WARNING" => warning_style,
                _ => info_style,
            },
        )
    });
    let logs = List::new(logs).block(
        Block::default()
            .borders(Borders::ALL)
            .title(" Recent Workflows "),
    );
    f.render_stateful_widget(logs, area, &mut app.recent.state);
}
