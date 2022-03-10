use config::{Config, ConfigError, Environment, File};
use serde::Deserialize;
use std::cmp::Ordering;
use std::fmt;
use std::ops::Mul;
use xdg::BaseDirectories;

#[derive(Debug, Deserialize)]
pub struct Layout {
    pub visible_notifs: u16,
}

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

#[derive(Clone, Copy, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub enum NotifService {
    Github,
}
impl fmt::Display for NotifService {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        fmt::Debug::fmt(self, f)
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

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct Notif {
    pub service: NotifService,
    pub token: String,
    #[serde(default)]
    pub refresh: Refresh,
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

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct VCSSlug(String);
impl Default for VCSSlug {
    fn default() -> Self {
        VCSSlug("gh".to_string())
    }
}
impl fmt::Display for VCSSlug {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct CCTray {
    pub url: String,
}

#[derive(Clone, Debug, Deserialize, Eq, Hash, PartialEq, PartialOrd)]
pub struct CircleCI {
    #[serde(default)]
    pub branch: Branch,
    pub token: String,
    #[serde(default)]
    pub vcs: VCSSlug,
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

#[derive(Clone, Debug, Deserialize, Eq, Hash, PartialEq, PartialOrd)]
pub struct Repo {
    // TODO: display: Enum { always, failing, ... }
    pub name: String,
    pub cctray: Option<CCTray>,
    pub circleci: Option<CircleCI>,
    #[serde(default)]
    pub refresh: Refresh,
}
impl Ord for Repo {
    fn cmp(&self, other: &Self) -> Ordering {
        match self.name.cmp(&other.name) {
            Ordering::Equal if self.cctray.is_some() => self.cctray.cmp(&other.cctray),
            Ordering::Equal if self.circleci.is_some() => self.circleci.cmp(&other.circleci),
            x => x,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub layout: Layout,
    pub logging: Logging,
    pub notifs: Option<Vec<Notif>>,
    pub repos: Vec<Repo>,
}

impl Settings {
    pub fn new() -> Result<Self, ConfigError> {
        let dirs = BaseDirectories::with_prefix("cctui").unwrap();
        let configfile = dirs
            .place_config_file("config.yml")
            .expect("cannot create configuration directory");
        let logfile = dirs
            .place_data_file("cctui.log")
            .expect("cannot create data directory");

        let builder = Config::builder()
            .set_default("layout.visible_notifs", 5)?
            .set_default("logging.file", logfile.to_str())?
            .set_default("logging.level", "INFO")?
            .add_source(File::from(configfile))
            .add_source(Environment::with_prefix("cctui"));
        // TODO: merge cli flags
        // https://github.com/mehcode/config-rs/issues/64
        match builder.build() {
            Ok(config) => config.try_deserialize(),
            Err(e) => Err(e)
        }
    }
}
