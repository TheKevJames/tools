mod display;
mod settings;
mod util;

use crate::{
    display::{ui, App},
    util::event::{Event, Events},
};
use settings::Settings;
use std::panic;
use std::{error::Error, io};
use termion::{event::Key, input::MouseTerminal, raw::IntoRawMode, screen::AlternateScreen};
use tui::{backend::TermionBackend, Terminal};

fn panic_hook(info: &std::panic::PanicInfo<'_>) {
    let location = info.location().unwrap(); // The current implementation always returns Some

    let msg = match info.payload().downcast_ref::<&'static str>() {
        Some(s) => *s,
        None => match info.payload().downcast_ref::<String>() {
            Some(s) => &s[..],
            None => "Box<Any>",
        },
    };
    println!(
        "{}thread '<unnamed>' panicked at '{}', {}\r",
        termion::screen::ToMainScreen,
        msg,
        location
    );
}

fn main() -> Result<(), Box<dyn Error>> {
    panic::set_hook(Box::new(panic_hook));

    let settings = match Settings::new() {
        Ok(s) => s,
        Err(e) => panic!("could not load settings: {:?}", e),
    };

    let events = Events::new();

    let stdout = io::stdout().into_raw_mode()?;
    let stdout = MouseTerminal::from(stdout);
    let stdout = AlternateScreen::from(stdout);
    let backend = TermionBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let mut app = App::new("CCTui", settings);
    loop {
        terminal.draw(|mut f| ui::draw(&mut f, &mut app))?;

        match events.next()? {
            Event::Input(key) => match key {
                Key::Char(c) => match c {
                    'q' => {
                        break;
                    }
                    _ => {}
                },
                _ => {}
            },
            Event::Tick => {
                app.on_tick();
            }
        }
    }

    Ok(())
}
