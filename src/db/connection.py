import pyodbc
from typing import Optional

class DatabaseConnection:
    """
    A class to manage database connections using pyodbc with context management support.
    """

    def __init__(self, server: str, database: str, username: str, password: str) -> None:
        """
        Initialize the DatabaseConnection object.

        Args:
            server (str): The server address.
            database (str): The name of the database.
            username (str): The username for authentication.
            password (str): The password for authentication.
        """
        self.server: str = server
        self.database: str = database
        self.username: str = username
        self.password: str = password
        self.connection: Optional[pyodbc.Connection] = None

    def __enter__(self) -> pyodbc.Connection:
        """
        Enter the context manager, establishing a database connection.

        Returns:
            pyodbc.Connection: The database connection object.
        """
        return self.connect()

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]) -> None:
        """
        Exit the context manager, closing the database connection.

        Args:
            exc_type (Optional[type]): The exception type (if any).
            exc_val (Optional[BaseException]): The exception value (if any).
            exc_tb (Optional[object]): The traceback object (if any).
        """
        self.disconnect()

    def connect(self) -> pyodbc.Connection:
        """
        Establish a connection to the database.

        Returns:
            pyodbc.Connection: The established database connection.

        Raises:
            pyodbc.Error: If the connection fails.
        """
        if self.connection is None:
            try:
                self.connection = pyodbc.connect(
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.server};DATABASE={self.database};"
                    f"UID={self.username};PWD={self.password};"
                    f"Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30"

                )
                print("Connection established successfully.")
            except pyodbc.Error as e:
                print(f"Error connecting to SQL Server: {e}")
                raise
        return self.connection

    def disconnect(self) -> None:
        """
        Close the database connection.
        """
        if self.connection:
            self.connection.close()
            print("Connection closed.")
            self.connection = None