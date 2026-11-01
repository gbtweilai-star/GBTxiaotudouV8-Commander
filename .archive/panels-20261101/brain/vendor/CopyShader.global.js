/* vendored from three@0.180.0 · **已转成经典脚本**（file:// 下 ESM 走不通）
   来源：vendor/node_modules/three/examples/jsm/CopyShader.js
   重建：py -3.14 tools/codex-scripts/vendor_three.py --write --classic
   第三方代码原样拷贝 + 机械 import/export 改写，不要在这里加业务逻辑。 */
(function (THREE) {
'use strict';
/* vendored from three@0.180.0 · 裸模块名已改为相对路径（壳的 CSP 不许 importmap）
   来源：vendor/node_modules/three/examples/jsm/shaders/CopyShader.js
   重建：py -3.14 tools/codex-scripts/vendor_three.py --write
   本文件是**第三方代码的原样拷贝 + 一处 import 改写**，不要在这里加业务逻辑。 */
/**
 * @module CopyShader
 * @three_import const {CopyShader} = THREE;
 */

/**
 * Full-screen copy shader pass.
 *
 * @constant
 * @type {ShaderMaterial~Shader}
 */
const CopyShader = {

	name: 'CopyShader',

	uniforms: {

		'tDiffuse': { value: null },
		'opacity': { value: 1.0 }

	},

	vertexShader: /* glsl */`

		varying vec2 vUv;

		void main() {

			vUv = uv;
			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,

	fragmentShader: /* glsl */`

		uniform float opacity;

		uniform sampler2D tDiffuse;

		varying vec2 vUv;

		void main() {

			vec4 texel = texture2D( tDiffuse, vUv );
			gl_FragColor = opacity * texel;


		}`

};

Object.assign(THREE, {CopyShader});

})(THREE);
