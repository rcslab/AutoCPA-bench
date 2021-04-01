--echo ########################################################################
--echo # ALTER TABLESPACE :    Unencrypted => Encrypted                       #
--echo ########################################################################
--echo # Set process to crash at page 10
SET SESSION debug= '+d,alter_encrypt_tablespace_page_10';

--echo # Encrypt the tablespace. It will cause crash.
--source include/expect_crash.inc
--error 0,CR_SERVER_LOST,ER_INTERNAL_ERROR
ALTER TABLESPACE encrypt_ts ENCRYPTION='Y';

--echo # RESTART $rc : WITH KEYRING PLUGIN after crash and cause resume operation
--echo #              to crash $crash_point_desc
let $NEW_CMD = $MYSQLD_CMD --log-error=$MYSQLTEST_VARDIR/log/my_restart.err --datadir=$MYSQLD_DATADIR --early-plugin-load=keyring_file=$KEYRING_PLUGIN --loose-keyring_file_data=$MYSQL_TMP_DIR/mysecret_keyring $KEYRING_PLUGIN_OPT --debug=+d,$crash_point;

--error 1,2,42,137
--exec $NEW_CMD
--inc $rc

# Following query should fail as server crashed during restart
--error CR_SERVER_GONE_ERROR
SELECT NAME, ENCRYPTION FROM INFORMATION_SCHEMA.INNODB_TABLESPACES WHERE NAME='encrypt_ts';

--echo # Search the pattern in error log
--source $MYSQLTEST_VARDIR/tmp/encryption_error_log.inc

--echo # RESTART $rc : Normal. In this restart resume operation should finish successfully
let $restart_parameters = restart: --early-plugin-load=keyring_file=$KEYRING_PLUGIN --loose-keyring_file_data=$MYSQL_TMP_DIR/mysecret_keyring $KEYRING_PLUGIN_OPT --log-error=$MYSQLTEST_VARDIR/log/my_restart.err;
--source include/start_mysqld_no_echo.inc
--inc $rc

--echo # Wait for Encryption processing to finish in background thread
let $wait_condition = SELECT ENCRYPTION = 'Y'
        FROM INFORMATION_SCHEMA.INNODB_TABLESPACES
        WHERE NAME='encrypt_ts';
--source include/wait_condition.inc

--echo # Search the pattern in error log
--source $MYSQLTEST_VARDIR/tmp/encryption_error_log.inc

SELECT * FROM t1 LIMIT 10;