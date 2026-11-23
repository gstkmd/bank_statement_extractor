package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"

	"github.com/ncruces/zenity"
)

const repoURL = "https://api.github.com/repos/gstkmd/ShieldDocs-Releases/releases/latest"

type Release struct {
	TagName string  `json:"tag_name"`
	Assets  []Asset `json:"assets"`
}

type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadUrl string `json:"browser_download_url"`
}

func main() {
	err := run()
	if err != nil {
		zenity.Error(fmt.Sprintf("Error: %v", err), zenity.Title("ShieldDocs Bootstrapper Error"))
	}
}

func run() error {
	// 1. Fetch latest release info
	resp, err := http.Get(repoURL)
	if err != nil {
		return fmt.Errorf("failed to check for updates: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GitHub API returned status: %v", resp.Status)
	}

	var release Release
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return fmt.Errorf("failed to parse release data: %v", err)
	}

	var downloadUrl string
	var assetName string
	for _, asset := range release.Assets {
		if len(asset.Name) > 4 && asset.Name[len(asset.Name)-4:] == ".exe" {
			downloadUrl = asset.BrowserDownloadUrl
			assetName = asset.Name
			break
		}
	}

	if downloadUrl == "" {
		return fmt.Errorf("no .exe asset found in the latest release")
	}

	// 2. Setup progress bar
	dlg, err := zenity.Progress(
		zenity.Title("Downloading ShieldDocs"),
	)
	if err != nil {
		return fmt.Errorf("failed to show progress dialog: %v", err)
	}
	defer dlg.Close()

	dlg.Text(fmt.Sprintf("Downloading %s...", release.TagName))

	// 3. Download file
	outPath := filepath.Join(os.TempDir(), assetName)
	out, err := os.Create(outPath)
	if err != nil {
		return fmt.Errorf("failed to create temporary file: %v", err)
	}
	defer out.Close()

	dlResp, err := http.Get(downloadUrl)
	if err != nil {
		return fmt.Errorf("failed to start download: %v", err)
	}
	defer dlResp.Body.Close()

	if dlResp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed with status: %v", dlResp.Status)
	}

	totalSize := dlResp.ContentLength
	buf := make([]byte, 32*1024)
	var downloaded int64

	for {
		n, err := dlResp.Body.Read(buf)
		if n > 0 {
			out.Write(buf[:n])
			downloaded += int64(n)
			if totalSize > 0 {
				percent := int((float64(downloaded) / float64(totalSize)) * 100)
				dlg.Value(percent)
				dlg.Text(fmt.Sprintf("Downloading %s... %d%%", release.TagName, percent))
			}
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error reading download stream: %v", err)
		}
	}
	
	dlg.Value(100)
	dlg.Text("Download complete! Launching...")

	// Close the file so it can be executed
	out.Close()

	// 4. Launch the application
	// We pass /SILENT and /FORCECLOSEAPPLICATIONS which the inno setup installer accepts.
	cmd := exec.Command(outPath, "/SILENT", "/FORCECLOSEAPPLICATIONS")
	err = cmd.Start()
	if err != nil {
		return fmt.Errorf("failed to launch application: %v", err)
	}

	return nil
}
