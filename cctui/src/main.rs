mod display;
mod poll;
mod settings;
mod util;

use crate::display::{ui, App};

use crossterm::ExecutableCommand;
use crossterm::event::{self, KeyCode, KeyEventKind};
use crossterm::terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen};
use log::debug;
use ratatui::prelude::{CrosstermBackend, Terminal};
use settings::Settings;
use std::error::Error;
use std::io::stdout;
use std::process::exit;
use std::str::FromStr;

fn main() -> Result<(), Box<dyn Error>> {
    let settings = match Settings::new() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("could not load settings: {:?}", e);
            exit(1);
        }
    };

    fern::Dispatch::new()
        .format(|out, message, record| {
            out.finish(format_args!(
                "[{}] [{}] [{}] {}",
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
                record.level(),
                record.target(),
                message
            ))
        })
        .level(log::LevelFilter::Warn)
        .level_for(
            "cctui",
            log::LevelFilter::from_str(&settings.logging.level.to_string())?,
        )
        .chain(fern::log_file(settings.logging.file.clone())?)
        .apply()?;

    stdout().execute(EnterAlternateScreen)?;
    enable_raw_mode()?;

    let mut terminal = Terminal::new(CrosstermBackend::new(stdout()))?;
    terminal.clear()?;
    terminal.hide_cursor()?;

    let mut app = App::new(&settings);
    debug!("starting app");
    loop {
        terminal.draw(|mut f| ui::draw(&mut f, &mut app))?;
        app.on_tick();

        if event::poll(std::time::Duration::from_millis(16))? {
            if let event::Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    let _acted = app.on_key(key);
                    if key.code == KeyCode::Char('q') {
                        debug!("quitting for user request");
                        break;
                    }
                }
            }
        }
    }

    stdout().execute(LeaveAlternateScreen)?;
    disable_raw_mode()?;
    Ok(())
}
