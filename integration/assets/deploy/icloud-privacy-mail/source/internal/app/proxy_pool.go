package app

import (
	"crypto/rand"
	"math/big"
	"net/http"
	"net/url"
	"os"
	"strings"
	"sync"
	"time"
)

// 代理池：proxyhub 的每个端口背后是一个住宅出口，单端口可用性约 80%，
// 因此按请求轮换，避免绑死在某个已失效的端口上。
//
// 未配置 IPM_PROXY_URLS 时返回 nil，调用方退回 http.DefaultTransport
// （其 Proxy: ProxyFromEnvironment 仍会读 HTTP_PROXY/HTTPS_PROXY）。
var (
	proxyPoolOnce   sync.Once
	proxyPoolURLs   []*url.URL
)

func proxyPool() []*url.URL {
	proxyPoolOnce.Do(func() {
		raw := strings.TrimSpace(os.Getenv("IPM_PROXY_URLS"))
		if raw == "" {
			return
		}
		for _, item := range strings.Split(raw, ",") {
			item = strings.TrimSpace(item)
			if item == "" {
				continue
			}
			parsed, err := url.Parse(item)
			if err != nil || parsed.Host == "" {
				continue
			}
			proxyPoolURLs = append(proxyPoolURLs, parsed)
		}
	})
	return proxyPoolURLs
}

func pickProxy() *url.URL {
	pool := proxyPool()
	if len(pool) == 0 {
		return nil
	}
	if len(pool) == 1 {
		return pool[0]
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(len(pool))))
	if err != nil {
		return pool[0]
	}
	return pool[n.Int64()]
}

// newRotatingTransport 返回一个每次建连都换出口的 Transport。
// 没有配置代理池时返回 nil，让调用方用默认 Transport。
func newRotatingTransport() *http.Transport {
	if len(proxyPool()) == 0 {
		return nil
	}
	base := http.DefaultTransport.(*http.Transport).Clone()
	base.Proxy = func(*http.Request) (*url.URL, error) {
		// Transport 每次新建连接时调用，HTTPS 的 CONNECT 隧道由它自己完成。
		return pickProxy(), nil
	}
	base.MaxIdleConnsPerHost = 1
	return base
}

func newHTTPClient(timeout time.Duration) *http.Client {
	client := &http.Client{Timeout: timeout}
	if transport := newRotatingTransport(); transport != nil {
		client.Transport = transport
	}
	return client
}
