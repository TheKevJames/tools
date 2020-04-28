use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub repos: Vec<String>,
    pub token: String,
}

impl Settings {
    pub fn new() -> Result<Self, ConfigError> {
        let mut s = Config::new();

        let dirs = BaseDirectories::with_prefix("cctui").unwrap();
        s.merge(File::from(dirs.get_config_home().join("config.yml")))?;
        s.merge(Environment::with_prefix("cctui"))?;

        s.try_into()
    }
}
