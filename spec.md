# vdx - Final Project Requirements

This document outlines the consolidated requirements for the `vdx` CLI tool, representing its complete, end-state functionality.

---

## 1. Core System & Authentication

*   **Authentication & Session Management:** The system must authenticate users via Username, Password, and Vault DNS, stored as an environment file. It will cache the resulting session locally and automatically intercept `INVALID_SESSION_ID` errors to renew expired sessions during API calls.
*   **API Version:** The tool must use Vault API. Beginning with version `v26.1` for all endpoint interactions to ensure feature compatibility.
*   **State & Ignore Tracking:** The system must maintain a local `.vdx_state.json` file to track MD5 checksums of deployed files for change detection. It must also support a `.vdxignore` file to bypass components matching specified wildcard patterns following .gitignore syntax. `login` resets the cache. A `clean` command explicitly removes the cache.
*   **Directory Structure:** The tool must use an expanded local project structure to isolate different asset types into dedicated top-level directories: `/components`, `/javasdk`, `/custom_pages`, and `/translations`.

---

## 2. Bidirectional Synchronization (`pull` & `push`)

The system must support pulling configurations from Vault and pushing local changes back to Vault for the following asset types.

*   **MDL Components (Metadata & Code):**
    *   **Pull:** Query and download MDL definitions for components belonging to only the `metadata` class (e.g., `DocumentType`, `Object`).
    *   **Push:** Detect local changes (new, modified, deleted) to MDL files and deploy them to Vault using the MDL API.

*   **Java SDK Code:**
    *   **Pull:** Query `code` class MDL components and download `com.veeva.vault.custom.*` files as as `.java` source files using the single source code file API `GET /api/{version}/code/{class_name}` to the local `/javasdk` directory. Organize into folders by package following java conventions.
    *   **Push:** Upload and deploy locally modified Java SDK files using the single file Vault Java SDK endpoints.

*   **Custom Page Distributions:**
    *   **Pull:** Retrieve all Client Code Distributions using `GET /api/{version}/uicode/distributions` and `GET /api/{version}/uicode/distributions/{distribution_name}/code` and unpack each ZIP files into the `/custom_pages` directory organized by distribution name.
    *   **Push:** Detect modifications in the `/custom_pages` directory and deploy these assets to update Custom Page distributions in Vault. Changes must be deployed as an entire dist in a zip to `POST /api/{version}/uicode/distributions/`

## Bulk Translations:
### Pull
1. Query for languages in the Vault 
2. For each Language, export file for each of the 4 message types using `POST /api/{version}/messages/{message_type}/language/{lang}/actions/export`,
3. Poll the jobs API for the job id returned completion adhering to the one call every 10s limit
4. Download the resulting translation archives into the `/translations` directory. Track the version of each row.

## Push 
    1. Create file of changed rows
    2. Deploy updated translation strings by uploading modified rows via the "Import Bulk Translation" API endpoint.
    3. One file per message type is fine.

---

## 3. VPK Packaging & Validation

*   **Comprehensive Packaging:** The `vdx package` command must dynamically bundle all locally modified assets—including MDL, Java SDK files, Custom Page distributions into a single, compliant Vault Package (VPK).. Translation files are not supported in vpk so package should export a file of only changed rows for manual import as a sibling to the vpk.
*   **Automated Validation:** The system must upload the generated VPK to the `/services/package` endpoint, poll for job completion, and automatically trigger a validation action on the resulting package.

## Data Model and APIs

### `vault_component__v`

* Stores all Vault Components
* Components have class of Metadata or Code
* Class can be determined by looking at the metadata of the component type `GET /api/{version}/metadata/components`
* mdl_definition__v stores MDL for Metadata Components
* mdl_definition__v can only be queried using the special component query endpoint `POST /api/{version}/query/components`

### Translations

* Message Types: `field_labels__sys`, `system_messages__sys`, `notification_template_messages__sys`, `user_account_messages__sys`
* Supported language codes: `SELECT admin_key__sys, name__v FROM language__sys`
* Export translation response example:

```json
{
	"responseStatus": "SUCCESS",
	"data": {
		"url": "/api/v24.3/services/jobs/385922",
		"jobId": "385922"
	}
}
```

* Example Job response when job is running:
```json
{
	"responseStatus": "SUCCESS",
	"data": {
		"id": 385827,
		"status": "RUNNING",
		"links": [
			{
				"rel": "self",
				"href": "/api/v24.3/services/jobs/385827",
				"method": "GET",
				"accept": "application/json"
			}
		],
		"created_by": 22318657,
		"created_date": "2026-02-26T00:45:47.000Z",
		"run_start_date": "2026-02-26T00:45:47.000Z"
	}
}
```
* Example response when job is complete. FIle should be downloaded using the content link forming the request using the attributes of the link:
```json
{
	"responseStatus": "SUCCESS",
	"data": {
		"id": 385827,
		"status": "SUCCESS",
		"links": [
			{
				"rel": "self",
				"href": "/api/v24.3/services/jobs/385827",
				"method": "GET",
				"accept": "application/json"
			},
			{
				"rel": "file",
				"href": "/api/v24.3/services/file_staging/items/V.E.R.N. Genomics- Custom Pages_English_Field-Labels_2-25-26_19-45-47.csv",
				"method": "GET",
				"accept": "application/json"
			},
			{
				"rel": "content",
				"href": "/api/v24.3/services/file_staging/items/content/V.E.R.N. Genomics- Custom Pages_English_Field-Labels_2-25-26_19-45-47.csv",
				"method": "GET",
				"accept": "application/octet-stream;charset=UTF-8"
			}
		],
		"created_by": 22318657,
		"created_date": "2026-02-26T00:45:47.000Z",
		"run_start_date": "2026-02-26T00:45:47.000Z",
		"run_end_date": "2026-02-26T00:45:51.000Z"
	}
}
```
