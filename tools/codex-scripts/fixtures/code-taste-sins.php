<?php
// 负对照 · PHP 侧（**只做行级判据**：结构度量与命名分析本器不做）

function exportAll(array $rows): string {
    try {
        return json_encode($rows);
    } catch (Exception $e) {
    }
}

function notReady(): void {
    // TODO: implement
}

function debugDump($payload) {
    var_dump($payload);
    return $payload;
}
