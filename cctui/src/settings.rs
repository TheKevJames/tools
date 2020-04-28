use serde::Deserialize;
use config::{Config,File};

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub repos: Vec<String>,
    pub token: String,
}

impl Settings {
    pub fn new() -> Self {
        let mut s = Config::new();

        //TODO: xdg
        s.merge(File::with_name("/Users/kevin/.config/cctui/config.yml"));
        //TODO: create with defaults if not exists
        //TODO: secrets
        //TODO: env vars

        //TODO: better way to do this?
        //docs recommend -> Result<Self, ConfigError>
        s.try_into().unwrap()
    }
}
