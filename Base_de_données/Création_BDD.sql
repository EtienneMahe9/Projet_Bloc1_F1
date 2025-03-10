CREATE TABLE CONSTRUCTORS (
  PRIMARY KEY (constructor_id),
  constructor_id VARCHAR(42) NOT NULL,
  name           VARCHAR(42),
  nationality    VARCHAR(42)
);

CREATE TABLE DRIVERS (
  PRIMARY KEY (driver_id),
  driver_id   VARCHAR(42) NOT NULL,
  name        VARCHAR(42),
  nationality VARCHAR(42)
);

CREATE TABLE DRIVE_FOR (
  PRIMARY KEY (driver_id, constructor_id),
  driver_id      VARCHAR(42) NOT NULL,
  constructor_id VARCHAR(42) NOT NULL
);

CREATE TABLE LAP_RECORDS (
  PRIMARY KEY (race_id, constructor_id),
  race_id          VARCHAR(42) NOT NULL,
  constructor_id   VARCHAR(42) NOT NULL,
  fastest_lap_rank VARCHAR(42)
);

CREATE TABLE PARTICIPATE_IN (
  PRIMARY KEY (driver_id, race_id),
  driver_id VARCHAR(42) NOT NULL,
  race_id   VARCHAR(42) NOT NULL,
  grid      VARCHAR(42)
);

CREATE TABLE RACES (
  PRIMARY KEY (race_id),
  race_id        VARCHAR(42) NOT NULL,
  year           VARCHAR(42),
  round          VARCHAR(42),
  race_name      VARCHAR(42),
  circuit        VARCHAR(42),
  date           VARCHAR(42),
  temperature    VARCHAR(42),
  humidity       VARCHAR(42),
  wind_speed     VARCHAR(42),
  wind_direction VARCHAR(42),
  precipitation  VARCHAR(42),
  pressure       VARCHAR(42)
);

CREATE TABLE RACE_RESULTS (
  PRIMARY KEY (race_id, driver_id),
  race_id           VARCHAR(42) NOT NULL,
  driver_id         VARCHAR(42) NOT NULL,
  position          VARCHAR(42),
  points            VARCHAR(42),
  race_time         VARCHAR(42),
  fastest_lap_time  VARCHAR(42),
  fastest_lap_speed VARCHAR(42)
);

CREATE TABLE RANKINGS (
  PRIMARY KEY (constructor_id, race_id),
  constructor_id VARCHAR(42) NOT NULL,
  race_id        VARCHAR(42) NOT NULL,
  points         VARCHAR(42),
  position       VARCHAR(42)
);

ALTER TABLE DRIVE_FOR ADD FOREIGN KEY (constructor_id) REFERENCES CONSTRUCTORS (constructor_id);
ALTER TABLE DRIVE_FOR ADD FOREIGN KEY (driver_id) REFERENCES DRIVERS (driver_id);

ALTER TABLE LAP_RECORDS ADD FOREIGN KEY (constructor_id) REFERENCES CONSTRUCTORS (constructor_id);
ALTER TABLE LAP_RECORDS ADD FOREIGN KEY (race_id) REFERENCES RACES (race_id);

ALTER TABLE PARTICIPATE_IN ADD FOREIGN KEY (race_id) REFERENCES RACES (race_id);
ALTER TABLE PARTICIPATE_IN ADD FOREIGN KEY (driver_id) REFERENCES DRIVERS (driver_id);

ALTER TABLE RACE_RESULTS ADD FOREIGN KEY (driver_id) REFERENCES DRIVERS (driver_id);
ALTER TABLE RACE_RESULTS ADD FOREIGN KEY (race_id) REFERENCES RACES (race_id);

ALTER TABLE RANKINGS ADD FOREIGN KEY (race_id) REFERENCES RACES (race_id);
ALTER TABLE RANKINGS ADD FOREIGN KEY (constructor_id) REFERENCES CONSTRUCTORS (constructor_id);
