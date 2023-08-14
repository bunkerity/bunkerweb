export default defineEventHandler(async (event) => {
  return [
    {
      id: "blacklist",
      name: "Blacklist",
      description:
        "Lorem ipsum dolor sit amet consectetur adipisicing elit. Vel vero, explicabo porro vitae nostrum distinctio repellat rerum perspiciatis delectus officiis praesentium numquam illo doloribus qui voluptates repellendus! Odit, doloremque ad!",
      version: "1.0",
      stream: "partial",
      settings: {
        USE_BLACKLIST: {
          context: "multisite",
          default: "yes",
          help: "Activate blacklist feature.",
          id: "use-blacklist",
          label: "Activate blacklisting",
          regex: "^(yes|no)$",
          type: "check",
        },
      },
      jobs: [
        {
          every: "hour",
          file: "blacklist-download.py",
          name: "blacklist-download",
          reload: true,
        },
      ],
    },
    {
      id: "antibot",
      name: "Antibot",
      description: "Deny",
      version: "1.0",
      stream: "partial",
      settings: {
        USE_ANTIBOT: {
          context: "multisite",
          default: "yes",
          help: "Activate blacklist feature.",
          id: "use-antibot",
          label: "Activate blacklisting",
          regex: "^(yes|no)$",
          type: "check",
        },
      },
      jobs: [
        {
          every: "hour",
          file: "blacklist-download.py",
          name: "blacklist-download",
          reload: true,
        },
      ],
    },
  ];
});
