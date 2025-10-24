import mysql.connector
from pymongo import MongoClient
import streamlit as st
import sys


def get_arg_value(arg_name):
    """Parses sys.argv to find the value for a given named argument."""
    try:
        # Example: streamlit run app.py -- --mysql-host localhost
        # sys.argv will be ['app.py', '--mysql-host', 'localhost']
        args = sys.argv
        arg_index = args.index(arg_name) + 1
        if arg_index < len(args):
            return args[arg_index]
        return None
    except ValueError:
        # This means the argument flag was not found
        return None


@st.cache_resource
def _create_mysql_connection():
    """Create and return a new MySQL connection object."""
    host = get_arg_value("--mysql-host")
    user = get_arg_value("--mysql-user")
    password = get_arg_value("--mysql-password")

    if not all([host, user, password]):
        st.error(
            "Fatal: MySQL host, user, or password not provided on the command line."
        )
        st.info("Please provide all required MySQL arguments.")
        st.code(
            "streamlit run app.py -- --mysql-host YOUR_HOST --mysql-user YOUR_USER --mysql-password YOUR_PASSWORD ..."
        )
        return None

    try:
        return mysql.connector.connect(
            host=host, user=user, password=password, database="mimic4"
        )
    except mysql.connector.Error as err:
        st.error(f"Error connecting to MySQL: {err}")
        st.warning("Please check your MySQL credentials and host availability.")
        return None


def get_mysql_connection():
    """Return an active MySQL connection, reconnecting if necessary."""
    def ensure_connection(connection_object):
        """Verify connection liveliness and reconnect when needed."""
        if connection_object is None:
            return None
        try:
            connection_object.ping(reconnect=True, attempts=3, delay=2)
            return connection_object
        except (AttributeError, mysql.connector.Error):
            return None

    connection = _create_mysql_connection()
    connection = ensure_connection(connection)
    if connection is not None:
        return connection

    _create_mysql_connection.clear()
    connection = ensure_connection(_create_mysql_connection())
    return connection


@st.cache_resource
def get_mongo_connection():
    """Establishes and returns a connection to the MongoDB database."""
    mongo_uri = get_arg_value("--mongo-uri")

    if not mongo_uri:
        st.error("Fatal: MongoDB connection URI not provided on the command line.")
        st.info("Please provide the --mongo-uri argument.")
        st.code("streamlit run app.py -- --mongo-uri YOUR_MONGO_URI ...")
        return None

    try:
        client = MongoClient(mongo_uri)
        db = client["mimiciv_note"]
        return db
    except Exception as e:
        st.error(f"Error connecting to MongoDB: {e}")
        st.warning("Please check your MongoDB connection URI.")
        return None
