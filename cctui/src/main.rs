mod display;
mod poll;
mod settings;
mod util;

use crate::display::{ui, App};
use crate::util::event::{Event, Events};

use log::debug;
use settings::Settings;
use std::error::Error;
use std::io::stdout;
use std::process::exit;
use std::str::FromStr;
use termion::{event::Key, input::MouseTerminal, raw::IntoRawMode, screen::AlternateScreen};
use tui::{backend::TermionBackend, Terminal};

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

    let events = Events::new();

    let stdout = stdout().into_raw_mode()?;
    let stdout = MouseTerminal::from(stdout);
    let stdout = AlternateScreen::from(stdout);
    let backend = TermionBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let mut app = App::new(&settings);
    debug!("starting app");
    loop {
        terminal.draw(|mut f| ui::draw(&mut f, &mut app))?;

        match events.next()? {
            Event::Input(key) => match key {
                Key::Char(c) => {
                    app.on_key(c);
                    if c == 'q' {
                        debug!("quitting for user request");
                        break;
                    }
                }
                _ => {}
            },
            Event::Tick => {
                app.on_tick();
            }
        }
    }

    Ok(())
}
