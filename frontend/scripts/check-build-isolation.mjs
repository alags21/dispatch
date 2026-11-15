import { constants } from "node:fs";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, relative, sep } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontend = dirname(dirname(fileURLToPath(import.meta.url)));
const parent = await mkdtemp(join(tmpdir(), "dispatch-build-isolation-"));
const repository = join(parent, "dispatch");
const app = join(repository, "frontend");
const excluded = new Set(["node_modules", ".next", ".git", "test-results", "playwright-report"]);

try {
  // Reproduce a WSL checkout beneath unrelated home-directory package files.
  await writeFile(join(parent, "package.json"), "");
  await writeFile(join(parent, "pnpm-lock.yaml"), "lockfileVersion: '9.0'\n");
  await mkdir(join(parent, "node_modules"));
  await mkdir(repository);
  const git = spawnSync("git", ["-c", "core.hooksPath=/dev/null", "init", "--quiet", repository]);
  if (git.status !== 0) throw new Error("Unable to initialize regression fixture repository");

  await cp(frontend, app, {
    recursive: true,
    filter(source) {
      const parts = relative(frontend, source).split(sep);
      return !parts.some((part) => excluded.has(part)) && !basename(source).startsWith(".env");
    },
  });
  // Copy dependencies physically: a symlink would resolve back into the original
  // checkout and fail to exercise the ancestor-directory bug.
  await cp(join(frontend, "node_modules"), join(app, "node_modules"), {
    recursive: true,
    verbatimSymlinks: true,
    mode: constants.COPYFILE_FICLONE,
  });
  const result = spawnSync(
    process.execPath,
    [join(app, "node_modules/next/dist/bin/next"), "build", "--webpack"],
    { cwd: app, stdio: "inherit", timeout: 180_000 },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error("Build isolation regression failed");
  if ((await readFile(join(parent, "package.json"), "utf8")) !== "") {
    throw new Error("Build modified the unrelated ancestor package.json");
  }
  console.log("PASS: production build ignores unrelated ancestor package files and node_modules.");
} finally {
  await rm(parent, { recursive: true, force: true });
}
