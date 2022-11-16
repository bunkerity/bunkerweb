"use strict";
Object.defineProperty(exports, "__esModule", {
    value: true
});
Object.defineProperty(exports, // DISABLE_TOUCH = TRUE
// Retrieve an existing context from cache if possible (since contexts are unique per
// source path), or set up a new one (including setting up watchers and registering
// plugins) then return it
"default", {
    enumerable: true,
    get: ()=>setupTrackingContext
});
const _fs = /*#__PURE__*/ _interopRequireDefault(require("fs"));
const _path = /*#__PURE__*/ _interopRequireDefault(require("path"));
const _fastGlob = /*#__PURE__*/ _interopRequireDefault(require("fast-glob"));
const _quickLru = /*#__PURE__*/ _interopRequireDefault(require("quick-lru"));
const _normalizePath = /*#__PURE__*/ _interopRequireDefault(require("normalize-path"));
const _hashConfig = /*#__PURE__*/ _interopRequireDefault(require("../util/hashConfig"));
const _getModuleDependencies = /*#__PURE__*/ _interopRequireDefault(require("../lib/getModuleDependencies"));
const _resolveConfig = /*#__PURE__*/ _interopRequireDefault(require("../public/resolve-config"));
const _resolveConfigPath = /*#__PURE__*/ _interopRequireDefault(require("../util/resolveConfigPath"));
const _sharedState = require("./sharedState");
const _setupContextUtils = require("./setupContextUtils");
const _parseDependency = /*#__PURE__*/ _interopRequireDefault(require("../util/parseDependency"));
const _validateConfigJs = require("../util/validateConfig.js");
function _interopRequireDefault(obj) {
    return obj && obj.__esModule ? obj : {
        default: obj
    };
}
let configPathCache = new _quickLru.default({
    maxSize: 100
});
let candidateFilesCache = new WeakMap();
function getCandidateFiles(context, tailwindConfig) {
    if (candidateFilesCache.has(context)) {
        return candidateFilesCache.get(context);
    }
    let candidateFiles = tailwindConfig.content.files.filter((item)=>typeof item === "string").map((contentPath)=>(0, _normalizePath.default)(contentPath));
    return candidateFilesCache.set(context, candidateFiles).get(context);
}
// Get the config object based on a path
function getTailwindConfig(configOrPath) {
    let userConfigPath = (0, _resolveConfigPath.default)(configOrPath);
    if (userConfigPath !== null) {
        let [prevConfig, prevConfigHash, prevDeps, prevModified] = configPathCache.get(userConfigPath) || [];
        let newDeps = (0, _getModuleDependencies.default)(userConfigPath).map((dep)=>dep.file);
        let modified = false;
        let newModified = new Map();
        for (let file of newDeps){
            let time = _fs.default.statSync(file).mtimeMs;
            newModified.set(file, time);
            if (!prevModified || !prevModified.has(file) || time > prevModified.get(file)) {
                modified = true;
            }
        }
        // It hasn't changed (based on timestamps)
        if (!modified) {
            return [
                prevConfig,
                userConfigPath,
                prevConfigHash,
                prevDeps
            ];
        }
        // It has changed (based on timestamps), or first run
        for (let file1 of newDeps){
            delete require.cache[file1];
        }
        let newConfig = (0, _resolveConfig.default)(require(userConfigPath));
        newConfig = (0, _validateConfigJs.validateConfig)(newConfig);
        let newHash = (0, _hashConfig.default)(newConfig);
        configPathCache.set(userConfigPath, [
            newConfig,
            newHash,
            newDeps,
            newModified
        ]);
        return [
            newConfig,
            userConfigPath,
            newHash,
            newDeps
        ];
    }
    // It's a plain object, not a path
    let newConfig1 = (0, _resolveConfig.default)(configOrPath.config === undefined ? configOrPath : configOrPath.config);
    newConfig1 = (0, _validateConfigJs.validateConfig)(newConfig1);
    return [
        newConfig1,
        null,
        (0, _hashConfig.default)(newConfig1),
        []
    ];
}
function resolvedChangedContent(context, candidateFiles, fileModifiedMap) {
    let changedContent = context.tailwindConfig.content.files.filter((item)=>typeof item.raw === "string").map(({ raw , extension ="html"  })=>({
            content: raw,
            extension
        }));
    for (let changedFile of resolveChangedFiles(candidateFiles, fileModifiedMap)){
        let content = _fs.default.readFileSync(changedFile, "utf8");
        let extension = _path.default.extname(changedFile).slice(1);
        changedContent.push({
            content,
            extension
        });
    }
    return changedContent;
}
function resolveChangedFiles(candidateFiles, fileModifiedMap) {
    let changedFiles = new Set();
    _sharedState.env.DEBUG && console.time("Finding changed files");
    let files = _fastGlob.default.sync(candidateFiles);
    for (let file of files){
        let prevModified = fileModifiedMap.has(file) ? fileModifiedMap.get(file) : -Infinity;
        let modified = _fs.default.statSync(file).mtimeMs;
        if (modified > prevModified) {
            changedFiles.add(file);
            fileModifiedMap.set(file, modified);
        }
    }
    _sharedState.env.DEBUG && console.timeEnd("Finding changed files");
    return changedFiles;
}
function setupTrackingContext(configOrPath) {
    return ({ tailwindDirectives , registerDependency  })=>{
        return (root, result)=>{
            let [tailwindConfig, userConfigPath, tailwindConfigHash, configDependencies] = getTailwindConfig(configOrPath);
            let contextDependencies = new Set(configDependencies);
            // If there are no @tailwind or @apply rules, we don't consider this CSS
            // file or its dependencies to be dependencies of the context. Can reuse
            // the context even if they change. We may want to think about `@layer`
            // being part of this trigger too, but it's tough because it's impossible
            // for a layer in one file to end up in the actual @tailwind rule in
            // another file since independent sources are effectively isolated.
            if (tailwindDirectives.size > 0) {
                // Add current css file as a context dependencies.
                contextDependencies.add(result.opts.from);
                // Add all css @import dependencies as context dependencies.
                for (let message of result.messages){
                    if (message.type === "dependency") {
                        contextDependencies.add(message.file);
                    }
                }
            }
            let [context] = (0, _setupContextUtils.getContext)(root, result, tailwindConfig, userConfigPath, tailwindConfigHash, contextDependencies);
            let candidateFiles = getCandidateFiles(context, tailwindConfig);
            // If there are no @tailwind or @apply rules, we don't consider this CSS file or it's
            // dependencies to be dependencies of the context. Can reuse the context even if they change.
            // We may want to think about `@layer` being part of this trigger too, but it's tough
            // because it's impossible for a layer in one file to end up in the actual @tailwind rule
            // in another file since independent sources are effectively isolated.
            if (tailwindDirectives.size > 0) {
                let fileModifiedMap = (0, _setupContextUtils.getFileModifiedMap)(context);
                // Add template paths as postcss dependencies.
                for (let fileOrGlob of candidateFiles){
                    let dependency = (0, _parseDependency.default)(fileOrGlob);
                    if (dependency) {
                        registerDependency(dependency);
                    }
                }
                for (let changedContent of resolvedChangedContent(context, candidateFiles, fileModifiedMap)){
                    context.changedContent.push(changedContent);
                }
            }
            for (let file of configDependencies){
                registerDependency({
                    type: "dependency",
                    file
                });
            }
            return context;
        };
    };
}
