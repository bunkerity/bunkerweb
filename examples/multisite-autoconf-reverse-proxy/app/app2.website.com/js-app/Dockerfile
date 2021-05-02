FROM node

COPY app/ /home/node/app

RUN cd /home/node/app && npm install && chown -R root:node /home/node/app && chmod -R 770 /home/node/app

WORKDIR /home/node/app

USER node

CMD ["node", "index.js"]
