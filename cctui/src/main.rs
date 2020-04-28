mod display;
mod util;

use crate::{
    display::{ui, App},
    util::event::{Event, Events},
};
use std::{error::Error, io};
use termion::{event::Key, input::MouseTerminal, raw::IntoRawMode, screen::AlternateScreen};
use tui::{backend::TermionBackend, Terminal};

fn main() -> Result<(), Box<dyn Error>> {
    let events = Events::new();

    let stdout = io::stdout().into_raw_mode()?;
    let stdout = MouseTerminal::from(stdout);
    let stdout = AlternateScreen::from(stdout);
    let backend = TermionBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    terminal.hide_cursor()?;

    let mut app = App::new("CCTui", true);
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
