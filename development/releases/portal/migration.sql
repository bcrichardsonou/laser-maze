-- Additive upgrade only. Never import the original schema again.
CREATE TABLE IF NOT EXISTS zp_releases (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 component_id BIGINT UNSIGNED NOT NULL,
 version VARCHAR(64) CHARACTER SET ascii NOT NULL,
 sha256 CHAR(64) CHARACTER SET ascii NOT NULL,
 manifest TEXT NOT NULL,
 bytes INT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY component_version(component_id,version),
 FOREIGN KEY(component_id) REFERENCES zp_components(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS zp_deployments (
 component_id BIGINT UNSIGNED NOT NULL,
 deployment_id CHAR(36) CHARACTER SET ascii NOT NULL,
 release_id BIGINT UNSIGNED NOT NULL,
 status ENUM('started','failed','verified') NOT NULL,
 firmware_version VARCHAR(64) NULL,
 python_version VARCHAR(64) NULL,
 reason VARCHAR(80) NULL,
 started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(component_id,deployment_id),
 FOREIGN KEY(component_id) REFERENCES zp_components(id),
 FOREIGN KEY(release_id) REFERENCES zp_releases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
