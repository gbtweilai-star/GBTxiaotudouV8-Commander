// 负对照 · JS/TS 侧的每一条「AI 代码味」（第二轮扩充版）

export function handleJson(input: unknown) {
  try {
    return JSON.parse(String(input));
  } catch (e) {} // ❌ P0-1 空 catch，吞掉且不留痕
}

export function debugPayload(payload: unknown) {
  console.log(payload); // ❌ P1-3 输出残留（非输出型文件）
  return payload as any; // ❌ P0-5 类型逃逸
}

// TODO: implement  ❌ P0-2 占位残留

const foo = 1; // ❌ P1-8 占位命名
const bar = 2;

// ❌ P1-14 JS 里出现 snake_case 局部名（既有约定通常是 camelCase）
const user_name = 1;
const order_id = 2;
const task_key = 3;

// ❌ P1-13 布尔名什么都没说（flag / result / temp 这类）
const flag = true;

export function checklist() {
  expect(true).toBe(true); // ❌ P0-4 恒真断言
}

export function shipIt() {
  // 已完成接线 ❌ P0-6 注释说谎（完成声明 + 空实现）
  throw new Error("not implemented");
}

class UserManager {} // ❌ P1-10 后缀滥用（三连）
class OrderHelper {}
class DateUtil {}

class Store {
  load(key: string) {
    return key;
  }
} // ❌ P1-12 单方法类

export function process(rows: string[]) {
  // ❌ P1-13b 超通用函数名
  return rows;
}

export function forward(name: string) {
  return loadRecord(name); // ❌ P1-12b 只转发参数的包装
}

export function loadRecord(name: string) {
  return { name };
}

export function repeatedCatches() {
  // ❌ P1-4 同一个 catch 体重复三次
  try {
    a();
  } catch (e) {
    report(e);
  }
  try {
    b();
  } catch (e) {
    report(e);
  }
  try {
    c();
  } catch (e) {
    report(e);
  }
}

export function createUser(name: string) {
  // create user record ❌ P1-9 叙述性注释
  const user = createUserRecord(name);
  return user;
}

export function createUserRecord(name: string) {
  return { name };
}

// ❌ P2-11 注释掉的代码块
// const old = compute(items);
// if (old > 0) {
//   emit(old);
// }

export function duplicated(x: number) {
  let total = 0;
  total = x + 1;
  total = total * 2;
  total = total - 3;
  total = total / 4;
  total = total + 5;
  total = total * 6;
  total = total - 7;
  total = total / 8;
  // ❌ P1-7 重复块（上面 8 行再来一遍）
  total = x + 1;
  total = total * 2;
  total = total - 3;
  total = total / 4;
  total = total + 5;
  total = total * 6;
  total = total - 7;
  total = total / 8;
  return total;
} // ❌ P2-12 闭合括号标签

export function longJs() {
  // ❌ P1-5 JS 侧函数过长（> 80 行）—— 这是第二轮补上的 M6
  const b1 = 1;
  const b2 = 2;
  const b3 = 3;
  const b4 = 4;
  const b5 = 5;
  const b6 = 6;
  const b7 = 7;
  const b8 = 8;
  const b9 = 9;
  const b10 = 10;
  const b11 = 11;
  const b12 = 12;
  const b13 = 13;
  const b14 = 14;
  const b15 = 15;
  const b16 = 16;
  const b17 = 17;
  const b18 = 18;
  const b19 = 19;
  const b20 = 20;
  const b21 = 21;
  const b22 = 22;
  const b23 = 23;
  const b24 = 24;
  const b25 = 25;
  const b26 = 26;
  const b27 = 27;
  const b28 = 28;
  const b29 = 29;
  const b30 = 30;
  const b31 = 31;
  const b32 = 32;
  const b33 = 33;
  const b34 = 34;
  const b35 = 35;
  const b36 = 36;
  const b37 = 37;
  const b38 = 38;
  const b39 = 39;
  const b40 = 40;
  const b41 = 41;
  const b42 = 42;
  const b43 = 43;
  const b44 = 44;
  const b45 = 45;
  const b46 = 46;
  const b47 = 47;
  const b48 = 48;
  const b49 = 49;
  const b50 = 50;
  const b51 = 51;
  const b52 = 52;
  const b53 = 53;
  const b54 = 54;
  const b55 = 55;
  const b56 = 56;
  const b57 = 57;
  const b58 = 58;
  const b59 = 59;
  const b60 = 60;
  const b61 = 61;
  const b62 = 62;
  const b63 = 63;
  const b64 = 64;
  const b65 = 65;
  const b66 = 66;
  const b67 = 67;
  const b68 = 68;
  const b69 = 69;
  const b70 = 70;
  const b71 = 71;
  const b72 = 72;
  const b73 = 73;
  const b74 = 74;
  const b75 = 75;
  const b76 = 76;
  const b77 = 77;
  const b78 = 78;
  const b79 = 79;
  const b80 = 80;
  const b81 = 81;
  const b82 = 82;
  const b83 = 83;
  const b84 = 84;
  const b85 = 85;
  return b85;
}

export function deepScan(rows: string[][]) {
  // ❌ P1-6 JS 侧嵌套过深（块深度 ≥ 5）
  for (const row of rows) {
    if (row) {
      for (const cell of row) {
        if (cell) {
          while (cell) {
            try {
              return cell;
            } catch (e) {
              break;
            }
          }
        }
      }
    }
  }
  return null;
}
