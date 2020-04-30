use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use std::cmp::Ordering;
use std::fmt;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub struct Logging {
    pub file: String,
    pub level: String, // TODO: validation
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Branch(String);
impl Default for Branch {
    fn default() -> Self {
        Branch("master".to_string())
    }
}
impl fmt::Display for Branch {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, Hash)]
pub struct Repo {
    pub name: String,
    #[serde(default)]
    pub branch: Branch,
    pub workflow: String,
}
impl Ord for Repo {
    fn cmp(&self, other: &Self) -> Ordering {
        match self.name.cmp(&other.name) {
            Ordering::Equal => match self.branch.cmp(&other.branch) {
                Ordering::Equal => self.workflow.cmp(&other.workflow),
                x => x,
            },
            x => x,
        }
    }
}
impl PartialOrd for Repo {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl PartialEq for Repo {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name
    }
}

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub logging: Logging,
    pub repos: Vec<Repo>,
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
