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
use termion::{event::Key, input::MouseTerminal, raw::IntoRawMode, screen::IntoAlternateScreen};
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
    let stdout = match MouseTerminal::from(stdout).into_alternate_screen() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("could not build terminal screen: {:?}", e);
            exit(1);
        }
    };

    let backend = TermionBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let mut app = App::new(&settings);
    debug!("starting app");
    loop {
        terminal.draw(|mut f| ui::draw(&mut f, &mut app))?;

        match events.next()? {
            Event::Input(key) => {
                let acted = app.on_key(key);
                if let Key::Char(c) = key {
                    if !acted && c == 'q' {
                        debug!("quitting for user request");
                        break;
                    }
                }
            }
            Event::Tick => {
                app.on_tick();
            }
        }
    }

    Ok(())
}
