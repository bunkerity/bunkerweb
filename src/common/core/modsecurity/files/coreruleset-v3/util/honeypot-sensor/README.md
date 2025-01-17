The purpose of these files is to turn your current ModSecurity host into
a pseudo-honeypot sensor by doing the following:

1. Instructs Apache to listen for traffic on multiple unused ports
      - 8000
      - 8080
      - 8888
2. Creates Apache virtual host containers to bind to these ports.
3. If any traffic is received on these ports, then ModSecurity will
   inspect the traffic by inheriting any rules specified in the main
   Apache configuration.
4. ModSecurity's Audit Engine will use the mlogc program to forward
   the audit log entry onto the ModSecurity Project's central logging
   server.
