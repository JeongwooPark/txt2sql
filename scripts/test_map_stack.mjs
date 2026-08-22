import { LayerStack, ANALYSIS_Z_BASE, ANALYSIS_Z_STEP } from "../llm2sql/webapp/static/js/map/stack.js";
import { padLonLatExtent } from "../llm2sql/webapp/static/js/map/core.js";
import { sldBody, shouldLabel } from "../llm2sql/webapp/static/js/map/styles.js";

const failed = [];
let passed = 0;
function ok(name, cond, detail = "") {
  if (cond) {
    passed += 1;
    console.log(`[ok] ${name}`);
  } else {
    failed.push(`${name}: ${detail}`);
    console.log(`[fail] ${name} ${detail}`);
  }
}

const stack = new LayerStack();
ok("add a", stack.add("a"));
ok("add b", stack.add("b"));
ok("add c", stack.add("c"));
ok("newest on top", JSON.stringify(stack.ids()) === JSON.stringify(["c", "b", "a"]));
const z = stack.zIndices();
ok("z order", z.c > z.b && z.b > z.a);
ok("z formula", z.c === ANALYSIS_Z_BASE + 3 * ANALYSIS_Z_STEP);
ok("move down", stack.moveDown("c") && JSON.stringify(stack.ids()) === JSON.stringify(["b", "c", "a"]));
ok("move up", stack.moveUp("c") && stack.ids()[0] === "c");
ok("move to", stack.moveTo("a", 0) && stack.ids()[0] === "a");
ok("remove", stack.remove("c") && !stack.has("c"));
ok("dup add", stack.add("a") === false);
ok("top stay", stack.moveUp("a") === false);

ok("label few", shouldLabel({ labelField: "A24", featureCount: 1 }));
ok("label many skip", !shouldLabel({ labelField: "A24", featureCount: 200 }));
ok("label bad field", !shouldLabel({ labelField: "A24;drop", featureCount: 1 }));
const labeled = sldBody("korDB:temp_x", { fill: "#ffcccc", stroke: "#ff4d4d", width: 3 }, {
  labelField: "A24",
  featureCount: 1,
});
ok("sld has text", labeled.includes("TextSymbolizer") && labeled.includes("A24"));
const unlabeled = sldBody("korDB:temp_x", { fill: "#ffcccc", stroke: "#ff4d4d", width: 2 }, {
  labelField: "A24",
  featureCount: 500,
});
ok("sld no text when many", !unlabeled.includes("TextSymbolizer"));
const padded = padLonLatExtent([129.09, 35.24, 129.0901, 35.2401]);
ok("js pad min span", padded[2] - padded[0] >= 0.003);

console.log(`\npassed=${passed} failed=${failed.length}`);
if (failed.length) {
  for (const item of failed) console.log(" -", item);
  process.exit(1);
}
