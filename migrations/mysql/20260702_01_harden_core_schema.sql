CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'member',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at VARCHAR(32) NOT NULL,
    updated_at VARCHAR(32) NOT NULL,
    created_at_dt DATETIME(6),
    updated_at_dt DATETIME(6),
    PRIMARY KEY (workspace_id, user_id),
    INDEX idx_workspace_members_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS storage_objects (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_user_id VARCHAR(64) NOT NULL,
    workspace_id VARCHAR(64) NOT NULL,
    object_type VARCHAR(64) NOT NULL,
    relative_path VARCHAR(1024) NOT NULL,
    relative_path_hash VARCHAR(64) NOT NULL,
    content_hash VARCHAR(128) NOT NULL,
    byte_size BIGINT NOT NULL DEFAULT 0,
    mime_type VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'ready',
    source_table VARCHAR(128),
    source_id BIGINT,
    created_at VARCHAR(32) NOT NULL,
    updated_at VARCHAR(32) NOT NULL,
    created_at_dt DATETIME(6),
    updated_at_dt DATETIME(6),
    UNIQUE KEY uq_storage_scope_path_hash (workspace_id, relative_path_hash),
    UNIQUE KEY uq_storage_scope_hash_type (workspace_id, object_type, content_hash),
    INDEX idx_storage_workspace_type_status (workspace_id, object_type, status),
    INDEX idx_storage_source (source_table, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
