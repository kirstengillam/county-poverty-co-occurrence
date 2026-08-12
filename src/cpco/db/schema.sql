-- One row per county per metric per year, keyed by 5-digit FIPS.
CREATE TABLE IF NOT EXISTS county_metrics (
    fips CHAR(5) NOT NULL,
    metric TEXT NOT NULL,
    year INT NOT NULL,
    value DOUBLE PRECISION,
    source TEXT NOT NULL,
    PRIMARY KEY (fips, metric, year)
);

-- One row per county, for joining metrics to a map point (TIGER/Line internal point).
CREATE TABLE IF NOT EXISTS counties (
    fips CHAR(5) PRIMARY KEY,
    name TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lon DOUBLE PRECISION NOT NULL
);
