## SemRepo-V2: RDF Triple Store Setup (Virtuoso)

This example demonstrates how to set up the SemRepo-V2 using [Virtuoso](https://virtuoso.openlinksw.com/) as the RDF triple store. 

### Requirements

- [Docker](https://www.docker.com/get-started) (includes Docker Compose)

### Running virtuoso

Download the RDF dump (.ttl) of the SemRepo-V2 from [Zenodo](https://doi.org/10.x/zenodo.x). For testing, we also provide a small sample subset data at [toLoad/](./toLoad) or [sample-data](../sample-data/) directory.

Make sure the RDF data is placed in the correct local directory; in the example [docker-compose](./virtuoso/docker-compose.yml) below, files must be located in ```/local/toLoad``` and mounted inside the container as:

```yaml
- /local/toLoad:/opt/virtuoso-opensource/database/toLoad
```

Then, start Virtuoso by running:
```bash
docker compose up -d
```

The password, ports, container name, etc. can be adjusted from the docker-compose file. Once the service is running, the service (including the SPARQL endpoint) will be available at: `http://localhost:8890`. The RDF data needs to be uploaded before we can explore them via SPARQL, see belows. 

### Uploading Data (.bash script)

We prepare a .bash script [`load_data.sh`](./load_data.sh) to automate the data upload. Adjust the local directory containing the RDF file and container name (should be the same as in the docker-compose file):

```
CONTAINER_NAME="semrepov2"
HOST_LOAD_DIR="/local/semrepov2/toLoad" # Host path (where the folders exist locally)
```

Make sure the file is executable ```chmod +x load_data.sh```, and then run:

```bash
 ./load_data.sh
```

The script will print the following output:
```
Checking directories...
Host and container directories OK.
Registering RDF files...
Registering folder: 100001_105000
Registering folder: 10001_15000
...
Found 40 folders.
Sending registration commands to Virtuoso...
OpenLink Virtuoso Interactive SQL (Virtuoso)
Version 07.20.3242 as of Oct 14 2025
Type HELP; for help and EXIT; to exit.
Connected to OpenLink Virtuoso
Driver: 07.20.3242 OpenLink Virtuoso ODBC Driver
SQL> 
Done. -- 1 msec.
SQL> 
Done. -- 1 msec.
....
Done. -- 1 msec.
SQL> Registration completed.
Starting RDF loader...
OpenLink Virtuoso Interactive SQL (Virtuoso)
Version 07.20.3242 as of Oct 14 2025
Type HELP; for help and EXIT; to exit.
Connected to OpenLink Virtuoso
Driver: 07.20.3242 OpenLink Virtuoso ODBC Driver
SQL> 
```

Depending on the file size, loading may take several minutes. Keep the terminal open until the process is complete. In the meantime, you can monitor the loading progress by checking the status of the files:

```sparql
SELECT
    ll_state,
    COUNT(*) AS files
FROM DB.DBA.LOAD_LIST
GROUP BY ll_state;
```

#### Monitoring Upload Progress
You can also monitor whether RDF loading is working properly by observing changes in the database file size.

Open a shell inside the container:

```
docker exec -it semrepov2 bash 
```

Check the size of the Virtuoso database:

```
ls -lh /opt/virtuoso-opensource/database/virtuoso.db
```

Run this command a few times; if the file size increases, data is still being loaded. You can also verify by running queries directly against the SPARQL endpoint: `http://localhost:8890/sparql/`

### Uploading Data (manual)

To load the data manually, first, enter the Virtuoso ISQL Shell

```
docker exec -it semrepov2 isql 1111 dba dba ##change the port, password, container name etc. depending on your setting in docker-compose
```

Then load a single RDF file:

```
ld_dir('/opt/virtuoso-opensource/database/toLoad', 'file.ttl', 'https://semrepo.org');
rdf_loader_run();
checkpoint;
```

Or load multiple files (all .ttl):

```
ld_dir('/opt/virtuoso-opensource/database/toLoad', '%.ttl', 'https://semrepo.org');
rdf_loader_run();
checkpoint;
```

Then monitor the progress as above.

### Other Settings

Additional configuration options for Virtuoso can be adjusted in the: ```virtuoso.ini```

This file allows you to modify settings such as

- Default SPARQL query shown in the endpoint UI
```
  DefaultQuery = SELECT (COUNT(*) AS ?count) FROM <https://semrepo.org> WHERE { ?s ?p ?o }
  ```
- Maximum SPARQL query execution time
```
MaxQueryExecutionTime = 10000	; in seconds
```
and other logging and performance options e.g., memory limits and buffer sizes, directory paths for database and RDF loading.
Edit the file as needed before starting the container, or rebuild/restart the service after making changes.
