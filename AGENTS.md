## Project Structure
- `./schema` contains a comprehensive description of mimic-iv datasets from original website. The corresponding table is imported to MySQL dataset mimic4. The schema file name corresponds to the table name.
- `db_connections.py` contains code to connect to MySQL and Mongo.
- `utils.py` contains helper code to query the database.
- `app.py` is the main Streamlit App for visualization.

## Code Style
- Use Black for Python formatting.
- Avoid abbreviations in variable names.
