use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use std::cmp::Ordering;
use std::fmt;
use std::ops::Mul;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub enum Level {
    ERROR,
    WARN,
    INFO,
    DEBUG,
    TRACE,
}
impl fmt::Display for Level {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        fmt::Debug::fmt(self, f)
    }
}

#[derive(Debug, Deserialize)]
pub struct Logging {
    pub file: String,
    pub level: Level,
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

#[derive(Clone, Debug, Deserialize, Eq, Hash, PartialEq, PartialOrd)]
pub struct CircleCI {
    #[serde(default)]
    pub branch: Branch,
    pub token: String,
    pub workflow: String,
}
impl Ord for CircleCI {
    fn cmp(&self, other: &Self) -> Ordering {
        match self.branch.cmp(&other.branch) {
            Ordering::Equal => self.workflow.cmp(&other.workflow),
            x => x,
        }
    }
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Refresh(u16);
impl Default for Refresh {
    fn default() -> Self {
        Refresh(60)
    }
}
// TODO: kludge
impl Mul<u16> for Refresh {
    type Output = u16;

    fn mul(self, rhs: u16) -> Self::Output {
        self.0.saturating_mul(rhs)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, PartialEq, PartialOrd)]
pub struct Repo {
    // TODO: display: Enum { always, failing, ... }
    pub name: String,
    pub circleci: Option<CircleCI>,
    #[serde(default)]
    pub refresh: Refresh,
}
impl Ord for Repo {
    fn cmp(&self, other: &Self) -> Ordering {
        match self.name.cmp(&other.name) {
            Ordering::Equal => self.circleci.cmp(&other.circleci),
            x => x,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub logging: Logging,
    pub repos: Vec<Repo>,
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
