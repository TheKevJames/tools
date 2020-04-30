use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub struct Logging {
    pub file: String,
    pub level: String,
}

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub logging: Logging,
    pub repos: Vec<String>,
    pub token: String,
}

impl Settings {
    pub fn new() -> Result<Self, ConfigError> {
        let mut s = Config::new();

        let dirs = BaseDirectories::with_prefix("cctui").unwrap();

        let logfile = dirs
            .place_data_file("cctui.log")
            .expect("cannot create data directory");
        s.set_default("logging.file", logfile.to_str())?;
        s.set_default("logging.level", "INFO")?;

        let configfile = dirs
            .place_config_file("config.yml")
            .expect("cannot create configuration directory");
        s.merge(File::from(configfile))?;

        s.merge(Environment::with_prefix("cctui"))?;

        // TODO: merge cli flags
        // https://github.com/mehcode/config-rs/issues/64

        s.try_into()
    }
}
