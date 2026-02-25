# vdx - Final Project Requirements

This document outlines the consolidated requirements for the `vdx` CLI tool, representing its complete, end-state functionality.

---

## 1. Core System & Authentication

*   **Authentication & Session Management:** The system must authenticate users via Username, Password, and Vault DNS. It will store the resulting session locally and automatically intercept `INVALID_SESSION_ID` errors to renew expired sessions during API calls.
*   **API Version:** The tool must use Vault API version `v26.1` for all endpoint interactions to ensure feature compatibility.
*   **State & Ignore Tracking:** The system must maintain a local `.vdx_state.json` file to track MD5 checksums of deployed files for change detection. It must also support a `.vdxignore` file to bypass components matching specified wildcard patterns.
*   **Directory Structure:** The tool must use an expanded local project structure to isolate different asset types into dedicated top-level directories: `/components`, `/javasdk`, `/custom_pages`, and `/translations`.

---

## 2. Bidirectional Synchronization (`pull` & `push`)

The system must support pulling configurations from Vault and pushing local changes back to Vault for the following asset types.

*   **MDL Components (Metadata & Code):**
    *   **Pull:** Query and download MDL definitions for components belonging to both `metadata` and `code` classes (e.g., `DocumentType`, `RecordTrigger`).
    *   **Push:** Detect local changes (new, modified, deleted) to MDL files and deploy them to Vault using the MDL API.

*   **Java SDK Code:**
    *   **Pull:** Query and download Vault Java SDK files (e.g., `.java` source files, JARs) to the local `/javasdk` directory.
    *   **Push:** Upload and deploy locally modified Java SDK files using the appropriate Vault Java SDK endpoints.

*   **Custom Page Distributions:**
    *   **Pull:** Retrieve Client Code Distribution metadata and download the associated web asset ZIP files into the `/custom_pages` directory.
    *   **Push:** Detect modifications in the `/custom_pages` directory and deploy these assets to update Custom Page distributions in Vault.

*   **Bulk Translations:**
    *   **Pull:** Trigger the "Export Bulk Translation File" job, poll for completion, and download the resulting translation archives into the `/translations` directory.
    *   **Push:** Deploy updated translation strings by uploading modified translation files via the "Import Bulk Translation" API endpoint.

---

## 3. VPK Packaging & Validation

*   **Comprehensive Packaging:** The `vdx package` command must dynamically bundle all locally modified assets—including MDL, Java SDK files, Custom Page distributions, and Translation files—into a single, compliant Vault Package (VPK).
*   **Automated Validation:** The system must upload the generated VPK to the `/services/package` endpoint, poll for job completion, and automatically trigger a validation action on the resulting package.
