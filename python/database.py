"""A two-slot connection pool restricted to the separate assignment database."""
import os
from contextlib import contextmanager
from pathlib import Path

import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATABASE_NAME = "little_lemon_database"


def load_config():
    load_dotenv(ROOT / ".env")
    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", ""),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", DATABASE_NAME),
    }
    if config["database"] != DATABASE_NAME:
        raise ValueError("MYSQL_DATABASE must be little_lemon_database; other schemas are refused.")
    if not config["user"] or not config["password"]:
        raise ValueError("Set MYSQL_USER and MYSQL_PASSWORD in the environment or private .env.")
    return config


def create_pool(config=None):
    dbconfig = dict(load_config() if config is None else config)
    if dbconfig.pop("database", DATABASE_NAME) != DATABASE_NAME:
        raise ValueError("Only the separate little_lemon_database database is allowed.")
    print("Connecting to MySQL database...")
    print("Creating connection pool...")
    try:
        # Omit database only for initial CREATE DATABASE through a pooled connection.
        pool = MySQLConnectionPool(
            pool_name="little_lemon_database_pool", pool_size=2, pool_reset_session=True,
            autocommit=False, charset="utf8mb4", connection_timeout=10,
            time_zone="+00:00", **dbconfig,
        )
    except Error as er:
        print("Error code:", er.errno)
        print("Error message:", er.msg)
        raise
    print("Connection established successfully.")
    print("The connection pool is created with a name:", pool.pool_name)
    print("The pool size is:", pool.pool_size)
    return pool


@contextmanager
def pooled_cursor(pool, use_database=True, dictionary=False):
    """Always close the cursor and return the connection, including failure paths.

    The caller commits intentional writes. Any remaining transaction is rolled
    back on exit; pooled sockets stay available for reuse until the process ends.
    """
    connection = cursor = None
    try:
        connection = pool.get_connection()
        print("Connection acquired from pool.")
        if use_database:
            connection.cmd_init_db(DATABASE_NAME)
        cursor = connection.cursor(dictionary=dictionary)
        yield connection, cursor
    except Error as er:
        print("Error code:", er.errno)
        print("Error message:", er.msg)
        raise
    finally:
        try:
            if cursor is not None:
                print("Closing cursor...")
                cursor.close()
        finally:
            if connection is not None:
                try:
                    if connection.in_transaction:
                        connection.rollback()
                        print("Uncommitted transaction rolled back.")
                finally:
                    connection.close()
                    print("Returning connection to pool...")


def split_sql_script(text):
    delimiter, pending = ";", []
    for line in text.splitlines():
        if line.strip().upper().startswith("DELIMITER "):
            if any(part.strip() and not part.lstrip().startswith("--") for part in pending):
                raise ValueError("Unfinished statement before DELIMITER.")
            delimiter = line.strip().split(None,1)[1]
            pending = []
            continue
        pending.append(line)
        if line.rstrip().endswith(delimiter):
            statement = "\n".join(pending).rstrip()[:-len(delimiter)].strip()
            if statement:
                yield statement
            pending = []
    if any(part.strip() and not part.lstrip().startswith("--") for part in pending):
        raise ValueError("Unfinished SQL statement.")


def execute_sql_script(pool, filename, use_database=True):
    from pathlib import Path
    path = (ROOT / "sql" / filename).resolve()
    if path not in {(ROOT/"sql"/n).resolve() for n in ("create_database.sql","schema.sql","seed_data.sql","stored_procedures.sql")}:
        raise ValueError("Only this project's SQL scripts may be executed.")
    with pooled_cursor(pool,use_database=use_database) as (connection,cursor):
        for statement in split_sql_script(path.read_text()):
            cursor.execute(statement)
            if cursor.with_rows:cursor.fetchall()
            while cursor.nextset():
                if cursor.with_rows:cursor.fetchall()
        connection.commit()
    print("SQL script committed:",path.name)


def initialize_database(pool):
    execute_sql_script(pool,"create_database.sql",use_database=False)
    execute_sql_script(pool,"schema.sql")
    print("Dedicated database and tables are available:",DATABASE_NAME)


def seed_bookings(pool):
    execute_sql_script(pool,"seed_data.sql")
    print("Supplemental booking fixtures available; these are not workbook bookings.")


PROCEDURES=("GetMaxQuantity","ManageBooking","UpdateBooking","AddBooking","CancelBooking")


def create_procedures(pool):
    execute_sql_script(pool,"stored_procedures.sql")
    print("Five required procedures available; existing definitions preserved.")


def call_procedure(pool,name,args=(),commit=False):
    if name not in PROCEDURES:raise ValueError("Unknown project procedure.")
    print("Calling",name)
    results=[]
    with pooled_cursor(pool) as (connection,cursor):
        cursor.callproc(name,args)
        for result in cursor.stored_results():
            try:
                rows=result.fetchall()
                results.append(rows)
                for row in rows:print(row)
            finally:result.close()
        if commit:
            connection.commit()
            print("Changes committed successfully.")
    return results
