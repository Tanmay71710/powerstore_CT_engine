from psycopg2 import connect, sql, OperationalError
from shared.log import get_logger

logger = get_logger(__name__)


class PostgresDB:
    """A PostgreSQL database interface class using psycopg2."""

    def __init__(self, host, dbname, user, password):
        """Initialize database connection parameters.

        :param host: Database host IP
        :type host: str
        :param dbname: Database name
        :type dbname: str
        :param user: Username
        :type user: str
        :param password: Password
        :type password: str
        """
        self.connection_params = {
            "host": host,
            "dbname": dbname,
            "user": user,
            "password": password,
        }
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establish a connection to the database."""
        try:
            self.conn = connect(**self.connection_params)
            self.cursor = self.conn.cursor()
        except OperationalError as e:
            logger.error("Connection failed: %s", e)
            raise

    def disconnect(self):
        """Close the connection to the database."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

    def _apply_conditions(self, query, where=None, order_by=None, limit=None):
        """Apply WHERE, ORDER BY, and LIMIT clauses to a SQL query.

        :param query: base SQL query to modify
        :type query: sql.SQL object
        :param where: filter conditions as a dictionary (e.g., {'column': 'value'})
        :type where: dict, optional
        :param order_by: columns to order results by
        :type order_by: list of str, optional
        :param limit: maximum number of records to fetch
        :type limit: int, optional
        :return: SQL query with applied conditions and list of parameters for placeholders
        :rtype: tuple(sql.SQL, list)
        """
        params = []

        if where:
            where_clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(
                [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in where.keys()]
            )
            query += where_clause
            params.extend(where.values())

        if order_by:
            order_by_clause = sql.SQL(" ORDER BY ") + sql.SQL(", ").join(
                [sql.Identifier(col) for col in order_by]
            )
            query += order_by_clause

        if limit:
            limit_clause = sql.SQL(" LIMIT ") + sql.Literal(limit)
            query += limit_clause

        return query, params

    def insert(self, table, data):
        """Insert a new record into a table.

        :param table: Table name
        :type table: str
        :param data: Data to insert, as a dictionary
        :type data: dict
        """
        columns = sql.SQL(', ').join(map(sql.Identifier, data.keys()))
        values = sql.SQL(', ').join(sql.Placeholder() * len(data))
        query = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
            table=sql.Identifier(table),
            columns=columns,
            values=values
        )
        try:
            self.cursor.execute(query, list(data.values()))
            self.conn.commit()
            logger.debug("Record inserted into %s.", table)
        except Exception as e:
            logger.error("Error inserting data: %s", e)
            self.conn.rollback()

    def select(self, table, columns=['*'], where=None, order_by=None, limit=None, to_dict=False):
        """Select specific columns from a table with optional conditions.

        :param table: Table name
        :type table: str
        :param columns: Columns to retrieve
        :type columns: list of str
        :param where: Filter conditions as a dictionary
        :type where: dict, optional
        :param order_by: Columns to order results by
        :type order_by: list of str, optional
        :param limit: Maximum number of records to fetch
        :type limit: int, optional
        :param to_dict: Return results as a list of dictionaries
        :type to_dict: bool, optional
        :return: Fetched records
        :rtype: list of tuples or list of dicts
        """
        fields = sql.SQL(', ').join(
            [sql.SQL('*')] if columns == ['*'] else map(sql.Identifier, columns)
        )
        query = sql.SQL("SELECT {fields} FROM {table}").format(
            fields=fields,
            table=sql.Identifier(table)
        )
        query, params = self._apply_conditions(query, where, order_by, limit)

        try:
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            if to_dict:
                col_names = [desc[0] for desc in self.cursor.description]
                results = [dict(zip(col_names, row)) for row in results]
            return results
        except Exception as e:
            logger.error("Error fetching data: %s", e)
            return []

    def update(self, table, data, where=None):
        """Update records in a table with specific conditions.

        :param table: Table name
        :type table: str
        :param data: Data to update, as a dictionary
        :type data: dict
        :param where: Filter conditions as a dictionary
        :type where: dict, optional
        """
        set_clause = sql.SQL(", ").join(
            [sql.SQL("{} = %s").format(sql.Identifier(k)) for k in data.keys()]
        )
        query = sql.SQL("UPDATE {table} SET {set_clause}").format(
            table=sql.Identifier(table),
            set_clause=set_clause
        )
        query, where_params = self._apply_conditions(query, where)
        params = list(data.values()) + where_params

        try:
            self.cursor.execute(query, params)
            logger.debug("Cursor status message: %s.", self.cursor.statusmessage)
            self.conn.commit()
            logger.debug("Record(s) updated in %s, %s.", table, params)
        except Exception as e:
            logger.error("Error updating data: %s", e)
            self.conn.rollback()

    def delete(self, table, where=None):
        """Delete records from a table with specific conditions.

        :param table: Table name
        :type table: str
        :param where: Filter conditions as a dictionary
        :type where: dict, optional
        """
        query = sql.SQL("DELETE FROM {table}").format(table=sql.Identifier(table))
        query, params = self._apply_conditions(query, where)

        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            logger.debug("Record(s) deleted from %s.", table)
        except Exception as e:
            logger.error("Error deleting data: %s", e)
            self.conn.rollback()

    def fetch_all(self, table, columns=['*'], to_dict=False):
        """Fetch all records from a table.

        :param table: Table name
        :type table: str
        :param columns: Columns to retrieve
        :type columns: list of str
        :param to_dict: Return results as a list of dictionaries
        :type to_dict: bool, optional
        :return: All records from the table
        :rtype: list of tuples or list of dicts
        """
        return self.select(table, columns, to_dict=to_dict)

    def delete_records_by_ids(self, table, ids_list):
        """Delete records from a table with specific conditions.

        :param table: Table name
        :type table: str
        :param where: Filter conditions as a dictionary
        :type where: dict, optional
        """
        query = sql.SQL(f"DELETE FROM {table} WHERE id IN %s")
        print(query)
        try:
            self.cursor.execute(query, (tuple(ids_list),))
            self.conn.commit()
            logger.debug("Record(s) deleted from %s.", table)
        except Exception as e:
            logger.error("Error deleting data: %s", e)
            self.conn.rollback()
