use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub logfile: String,
    pub loglevel: String,
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
        s.set_default("logfile", logfile.to_str())?;
        s.set_default("loglevel", "DEBUG")?; //TODO: change to INFO

        let configfile = dirs
            .place_config_file("config.yml")
            .expect("cannot create configuration directory");
        s.merge(File::from(configfile))?;

        s.merge(Environment::with_prefix("cctui"))?;

        //TODO: merge cli flags

        s.try_into()
    }
}
