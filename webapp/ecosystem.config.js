module.exports = {
  apps: [
    {
      name: "multi-ai-agent-app",
      cwd: "/home/socket9companylimited/projects/multi-ai-agent/webapp",
      script: "npx",
      args: "next start -p 3001",
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
