import { isAbsolute, relative, sep } from "node:path";

// Keep normal nested dependency resolution, but stop ancestor node_modules
// directories outside this app from supplying packages or package metadata.
export function moduleBoundary(root) {
  return {
    apply(resolver) {
      resolver.getHook("module").tapAsync(
        { name: "DispatchModuleBoundary", stage: -100 },
        (request, _context, callback) => {
          if (request.path) {
            const offset = relative(root, request.path);
            if (
              offset === ".." ||
              offset.startsWith(`..${sep}`) ||
              isAbsolute(offset)
            ) {
              return callback(null, null);
            }
          }
          callback();
        },
      );
    },
  };
}
