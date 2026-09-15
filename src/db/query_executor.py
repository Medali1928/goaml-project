import pyodbc
import time
import pandas as pd
import logging
from typing import Optional, List
from src.helpers.utils import clean_dataframe

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class QueryExecutor:
    """
    A class to execute SQL queries using a provided pyodbc connection and optionally convert results to pandas DataFrames.
    """

    def __init__(self, connection: pyodbc.Connection) -> None:
        """
        Initialize the QueryExecutor with an active database connection.

        Args:
            connection (pyodbc.Connection): An active pyodbc connection.
        """
        self.connection: pyodbc.Connection = connection

    def execute_query(self, query: str) -> Optional[pyodbc.Cursor]:
        """
        Execute a SQL query and return a cursor object.

        Args:
            query (str): The SQL query to execute.

        Returns:
            Optional[pyodbc.Cursor]: The cursor object if the query is successful; None otherwise.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            logging.info(f"Successfully executed query: {query}")
            return cursor
        except pyodbc.Error as e:
            logging.error(f"Error executing query: {e}")
            return None

    def fetch_all(self, cursor: pyodbc.Cursor) -> List[tuple]:
        """
        Fetch all rows from the given cursor object.

        Args:
            cursor (pyodbc.Cursor): The cursor object from which to fetch rows.

        Returns:
            List[tuple]: A list of tuples representing the rows, or an empty list if an error occurs.
        """
        try:
            rows = cursor.fetchall()
            logging.info("Successfully fetched all rows from the cursor.")
            return rows
        except pyodbc.Error as e:
            logging.error(f"Error fetching data: {e}")
            return []

    def execute_query_to_dataframe(self, query: str) -> pd.DataFrame:
        """
        Execute a SQL query and return the result as a pandas DataFrame.

        Args:
            query (str): The SQL query to execute.

        Returns:
            pd.DataFrame: A DataFrame containing the query results, or an empty DataFrame if an error occurs.
        """
        try:
            cursor = self.execute_query(query)
            if cursor is None:
                logging.warning(f"No data returned for query: {query}")
                return pd.DataFrame()  # Return an empty DataFrame if query execution fails

            # Fetch column names and rows
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Convert rows to DataFrame
            df = pd.DataFrame([tuple(row) for row in rows], columns=columns)
            logging.info(f"Successfully converted query result to DataFrame for query: {query}")
            return df
        except pyodbc.Error as e:
            logging.error(f"Error executing query to dataframe: {e}")
            return pd.DataFrame()  # Return an empty DataFrame in case of error
        
    def retry_query_execution(self, query: str, connection, max_attempts: int = 1, delay: int = 5) -> pd.DataFrame:
        """
        Executes a query with retry logic.

        Args:
            query (str): The SQL query to execute.
            connection: The database connection object.
            max_attempts (int): The maximum number of attempts. Default is 3.
            delay (int): Delay in seconds between retries. Default is 5.

        Returns:
            pd.DataFrame: DataFrame containing the query results. Empty DataFrame if all attempts fail.
        """
        attempts = 0

        while attempts < max_attempts:
            try:
                query_executor = QueryExecutor(connection)
                df = query_executor.execute_query_to_dataframe(query)
                if not df.empty:
                    return clean_dataframe(df)
            except Exception as e:
                logging.warning("Attempt %d failed for query: %s. Error: %s", attempts + 1, query, e)
            
            attempts += 1
            time.sleep(delay)

        logging.warning("Failed to execute query after %d attempts", max_attempts)
        return pd.DataFrame()
