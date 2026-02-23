# 1. System Hardening
sudo ./vps-system-hardening.sh

# 2. Reboot
sudo reboot

# 3. PostgreSQL
sudo ./postgres.sh

# 4. DuckDB  
sudo ./duckdb.sh

# 5. Redis
sudo ./redis.sh

# 6. Airflow
sudo ./airflow.sh

# 7. Nginx + React (with rate limiting)
sudo ./nginx.sh

# 8. Migrate secrets to env vars
sudo ./secrets-to-env.sh

# 9. Set up monitoring
sudo ./monitoring.sh

# 10. Test everything!
sudo /usr/local/bin/system-monitor.sh
tail -f /var/log/system-monitoring.log
```