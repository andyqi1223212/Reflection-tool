# Inquiry Chain · Your Card Library

> This is your starter card library. Replace this file with your own as you accumulate cards.
>
> **How cards land here**: when `agents_runtime.orchestrate` finishes a run with `verdict: "pass"`, the push stage appends the new card as a `### IC-NNN` section below.
>
> **After editing manually**: run `python3 tools/export_v3_chains.py` to regenerate `data/chains.json` (and `crystallization-prototype/chains.data.js` for the reading UI).

---

## 0. About this format

Each card is one `### IC-NNN: 一句话标题` block with the following sections:

- **Crystallization** — the core: `机制 / 入口句 / 小动作`（mechanism / anchor / micro_steps）
- **Pattern tags** — pattern codes from your schema
- **Axis** — `judgment` or `attention` (per `context/crystallization-schema-v0.md`)
- **Source refs** — pointers back to the conversation that produced this card
- `<details>` block — trigger and the original question chain

See `context/crystallization-schema-v0.md` for the full schema.

---

## 1. Trigger-Time Index

> When you're triggered, find the closest entry here and read the anchor. Don't read mechanism unless you have time.

(Add your entries here, e.g.)

### When I procrastinate on weekends

> 是身体在还自由账。

相关：`IC-001`

---

## 2. Cards

### IC-001：周末计划学习却刷手机一整天，周日晚上焦虑

**Crystallization**

机制：你不是自制力差，是在用周末的刷手机补偿工作日欠下的自由账。工作日被任务推着走，没有一刻真正属于自己，身体就把周末当成唯一可以释放"不计划"信号的窗口。你越规划学习，它越反弹——因为对神经系统来说，计划等同于继续剥夺自由。

入口句：

> 是身体在还自由账。

小动作：

1. 每个工作日找 5 分钟完全为自己，不学习不工作。
2. 周末想刷手机时，先站起来走几步再决定。
3. 周日晚上焦虑时，默念：身体在还自由账。

**Pattern tags**：`P-KNOW-DO` `P-EFF` `P-SPIRAL`

**Axis**：`attention`

**Source refs**：example synthetic conversation

<details>
<summary>Trigger / 追问路径</summary>

**Trigger**：每个周末都计划好要看书、运动、学新东西，但一到周六就开始刷手机，刷一整天，周日晚上又开始焦虑，恶性循环。

**追问路径**：

- 是不是就是单纯的自制力差？
- 那我周末还是要躺平咯？

</details>

---

<!-- Add more cards below following the same format.
     Or just run the pipeline — it will append here automatically. -->
