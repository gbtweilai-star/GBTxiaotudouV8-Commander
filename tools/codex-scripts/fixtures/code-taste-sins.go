package store

// 负对照 · Go 侧（**只做行级判据**）

func ExportAll(rows []Row) (string, error) {
	data, err := json.Marshal(rows)
	if err != nil {
	}
	return string(data), nil
}

func NotReady() string {
	// not implemented
	return ""
}
