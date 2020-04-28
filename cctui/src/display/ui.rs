use tui::{
    backend::Backend,
    layout::{Constraint, Layout, Rect},
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
    // Draw logs
    let info_style = Style::default().fg(Color::White);
    let warning_style = Style::default().fg(Color::Yellow);
    let error_style = Style::default().fg(Color::Magenta);
    let critical_style = Style::default().fg(Color::Red);
    let logs = app.recent.items.iter().map(|&(evt, level)| {
        Text::styled(
            format!("{}: {}", level, evt),
            match level {
                "ERROR" => error_style,
                "CRITICAL" => critical_style,
                "WARNING" => warning_style,
                _ => info_style,
            },
        )
    });
    let logs = List::new(logs).block(Block::default().borders(Borders::ALL).title(" Repo Status "));
    f.render_stateful_widget(logs, area, &mut app.recent.state);
}

fn draw_recent<B: Backend>(f: &mut Frame<B>, app: &mut App, area: Rect) {
    // Draw logs
    let info_style = Style::default().fg(Color::White);
    let warning_style = Style::default().fg(Color::Yellow);
    let error_style = Style::default().fg(Color::Magenta);
    let critical_style = Style::default().fg(Color::Red);
    let logs = app.recent.items.iter().map(|&(evt, level)| {
        Text::styled(
            format!("{}: {}", level, evt),
            match level {
                "ERROR" => error_style,
                "CRITICAL" => critical_style,
                "WARNING" => warning_style,
                _ => info_style,
            },
        )
    });
    let logs = List::new(logs).block(Block::default().borders(Borders::ALL).title(" Recent Workflows "));
    f.render_stateful_widget(logs, area, &mut app.recent.state);
}
