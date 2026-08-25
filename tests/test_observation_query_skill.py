import sqlite3

import pytest
from app.assistant_schemas import AssistantSqlQuery
from app.observation_query_skill import ObservationQueryError, ObservationQueryExecutor


def query_database(tmp_path):
    path = tmp_path / "archive.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE observations (
            id INTEGER PRIMARY KEY, observed_at TEXT, season TEXT, locality TEXT,
            country_name TEXT, admin1_name TEXT, notes TEXT
        );
        CREATE TABLE observation_species (
            id INTEGER PRIMARY KEY, observation_id INTEGER, species_id INTEGER,
            subspecies_id INTEGER, photo_type TEXT, sex TEXT, life_stage TEXT,
            notes TEXT, is_primary INTEGER
        );
        CREATE TABLE species (
            id INTEGER PRIMARY KEY, genus_id INTEGER, chinese_name TEXT,
            scientific_name TEXT
        );
        CREATE TABLE genera (
            id INTEGER PRIMARY KEY, family_id INTEGER, chinese_name TEXT,
            scientific_name TEXT
        );
        CREATE TABLE families (
            id INTEGER PRIMARY KEY, order_id INTEGER, chinese_name TEXT,
            scientific_name TEXT
        );
        CREATE TABLE taxonomic_orders (
            id INTEGER PRIMARY KEY, chinese_name TEXT, scientific_name TEXT
        );
        CREATE TABLE subspecies (
            id INTEGER PRIMARY KEY, chinese_name TEXT, scientific_name TEXT
        );
        CREATE TABLE observation_location_links (observation_id INTEGER, location_id INTEGER);
        CREATE TABLE birding_locations (
            id INTEGER PRIMARY KEY, name TEXT, city TEXT, district TEXT
        );
        CREATE TABLE observation_trip_links (observation_id INTEGER, trip_id INTEGER);
        CREATE TABLE birding_trips (id INTEGER PRIMARY KEY, name TEXT, location_id INTEGER);

        INSERT INTO taxonomic_orders VALUES (1, '雀形目', 'Passeriformes');
        INSERT INTO families VALUES (1, 1, '鹎科', 'Pycnonotidae');
        INSERT INTO families VALUES (2, 1, '鸦科', 'Corvidae');
        INSERT INTO genera VALUES (1, 1, '鹎属', 'Pycnonotus');
        INSERT INTO genera VALUES (2, 2, '灰喜鹊属', 'Cyanopica');
        INSERT INTO species VALUES (1, 1, '白头鹎', 'Pycnonotus sinensis');
        INSERT INTO species VALUES (2, 2, '灰喜鹊', 'Cyanopica cyanus');
        INSERT INTO observations VALUES
            (1, '2024-04-05 08:00:00', 'spring', '湖边', '中国', '浙江省', NULL),
            (2, '2024-04-05 09:00:00', 'spring', '林地', '中国', '浙江省', NULL),
            (3, '2024-04-06 09:00:00', 'spring', '湖边', '中国', '浙江省', NULL);
        INSERT INTO observation_species VALUES
            (1, 1, 1, NULL, 'individual', 'male', 'adult', NULL, 1),
            (2, 2, 2, NULL, 'individual', 'unknown', 'adult', NULL, 1),
            (3, 3, 1, NULL, 'individual', 'female', 'adult', NULL, 1),
            (4, 3, 2, NULL, 'individual', 'unknown', 'adult', NULL, 0);
        """
    )
    connection.commit()
    connection.close()
    return path


def plan(sql, parameters=None):
    return AssistantSqlQuery(
        interpretation="测试查询",
        sql=sql,
        parameters=parameters or {},
        sort="desc",
    )


def test_query_skill_supports_exact_day_and_multiple_species(tmp_path):
    executor = ObservationQueryExecutor(query_database(tmp_path))
    result = executor.execute(
        plan(
            """SELECT DISTINCT o.observation_id
            FROM field_observations o
            JOIN field_observation_taxa t USING (observation_id)
            WHERE o.observed_date = :day
              AND t.species_chinese_name IN (:first_species, :second_species)""",
            {
                "day": "2024-04-05",
                "first_species": "白头鹎",
                "second_species": "灰喜鹊",
            },
        )
    )

    assert set(result.observation_ids) == {1, 2}


def test_query_skill_supports_same_photo_and_family_queries(tmp_path):
    executor = ObservationQueryExecutor(query_database(tmp_path))
    same_photo = executor.execute(
        plan(
            """SELECT observation_id FROM field_observation_taxa
            WHERE species_chinese_name IN (:first_species, :second_species)
            GROUP BY observation_id
            HAVING COUNT(DISTINCT species_chinese_name) = 2""",
            {"first_species": "白头鹎", "second_species": "灰喜鹊"},
        )
    )
    family = executor.execute(
        plan(
            "SELECT observation_id FROM field_observation_taxa WHERE family_chinese_name = :family",
            {"family": "鸦科"},
        )
    )

    assert same_photo.observation_ids == [3]
    assert set(family.observation_ids) == {2, 3}


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM observations RETURNING id AS observation_id",
        "SELECT id AS observation_id FROM observations",
        "SELECT observation_id FROM field_observations; PRAGMA database_list",
        "ATTACH DATABASE 'secret.sqlite' AS secret SELECT 1 AS observation_id",
    ],
)
def test_query_skill_rejects_writes_raw_tables_and_multiple_statements(tmp_path, sql):
    executor = ObservationQueryExecutor(query_database(tmp_path))

    with pytest.raises(ObservationQueryError):
        executor.execute(plan(sql))
